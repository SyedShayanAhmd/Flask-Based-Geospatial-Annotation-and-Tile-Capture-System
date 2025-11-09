# app.py
import os
import json
import io
import time
import traceback
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_from_directory
import requests
from PIL import Image, UnidentifiedImageError
import mercantile
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# Config
# -----------------------------
TILE_SERVERS = {
    "ESRI World Imagery": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "Google Satellite": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "Google Hybrid": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    "Google Roads": "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    "Google Terrain": "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
    "OpenStreetMap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "OpenTopoMap": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
    "CartoDB Dark": "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    "CartoDB Light": "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
}
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible)'}
TILE_SIZE = 256
CAPTURE_DIR = os.path.join(os.getcwd(), "captures")
DB_FILE = os.path.join(os.getcwd(), "polygons_db.json")
os.makedirs(CAPTURE_DIR, exist_ok=True)

# Category definitions
CATEGORIES = [
    {
        "name": "rooftop",
        "type": "any",
        "attributes": []
    },
    {
        "name": "rooftop free",
        "type": "any",
        "attributes": []
    },
    {
        "name": "rooftop obs",
        "type": "any",
        "attributes": []
    },
    {
        "name": "street",
        "type": "any",
        "attributes": []
    },
    {
        "name": "ground",
        "type": "any",
        "attributes": []
    },
    {
        "name": "PV",
        "type": "any",
        "attributes": []
    },
    {
        "name": "water",
        "type": "any",
        "attributes": []
    },
    {
        "name": "trees",
        "type": "any",
        "attributes": []
    },
    {
        "name": "grass",
        "type": "any",
        "attributes": []
    }
]

# Color mapping for each category
CATEGORY_COLORS = {
    "rooftop": '#e6194b',
    "rooftop free": '#3cb44b', 
    "rooftop obs": '#ffe119',
    "street": '#4363d8',
    "ground": '#f58231',
    "PV": '#911eb4',
    "water": '#42d4f4',
    "trees": '#bfef45',
    "grass": '#fabed4'
}

# Ensure DB exists
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump([], f)

app = Flask(__name__, static_folder="captures", static_url_path="/captures")

# -----------------------------
# Helpers
# -----------------------------
def load_db():
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def timestamp_str():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _download_one_tile(url, timeout, tries=2, delay=0.25):
    last_exc = None
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                ctype = r.headers.get("Content-Type", "")
                if "image" in ctype:
                    try:
                        return Image.open(io.BytesIO(r.content)).convert("RGB")
                    except UnidentifiedImageError as ue:
                        last_exc = ue
                else:
                    last_exc = RuntimeError(f"Not an image (Content-Type={ctype})")
            else:
                last_exc = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:
            last_exc = e
        time.sleep(delay)
    print(f"[TILE FAILED] {url} -> {last_exc}")
    return Image.new("RGB", (TILE_SIZE, TILE_SIZE), (200, 200, 200))

def download_tile(x, y, z, tile_server_url, timeout=12):
    url = tile_server_url.format(x=x, y=y, z=z)
    return _download_one_tile(url, timeout=timeout, tries=3, delay=0.2)

def stitch_tiles_for_bounds(min_lon, min_lat, max_lon, max_lat, zoom, tile_server_url):
    tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, zoom))
    if not tiles:
        mid_lon = (min_lon + max_lon) / 2.0
        mid_lat = (min_lat + max_lat) / 2.0
        center_tile = mercantile.tile(mid_lon, mid_lat, zoom)
        tiles = [center_tile]

    min_x = min(t.x for t in tiles)
    max_x = max(t.x for t in tiles)
    min_y = min(t.y for t in tiles)
    max_y = max(t.y for t in tiles)

    width_px = (max_x - min_x + 1) * TILE_SIZE
    height_px = (max_y - min_y + 1) * TILE_SIZE
    stitched = Image.new("RGB", (width_px, height_px))

    tile_coords = [(tx, ty) for tx in range(min_x, max_x + 1) for ty in range(min_y, max_y + 1)]

    results = {}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(tile_coords)))) as exe:
        futures = {exe.submit(download_tile, tx, ty, zoom, tile_server_url): (tx, ty) for (tx, ty) in tile_coords}
        for fut in as_completed(futures):
            tx, ty = futures[fut]
            try:
                img = fut.result()
            except Exception as e:
                print(f"[Thread tile error] {tx},{ty} -> {e}")
                img = Image.new("RGB", (TILE_SIZE, TILE_SIZE), (200,200,200))
            results[(tx, ty)] = img

    for tx in range(min_x, max_x + 1):
        for ty in range(min_y, max_y + 1):
            img = results.get((tx, ty), Image.new("RGB", (TILE_SIZE, TILE_SIZE), (200,200,200)))
            x_px = (tx - min_x) * TILE_SIZE
            y_px = (ty - min_y) * TILE_SIZE
            stitched.paste(img, (x_px, y_px))

    meta = {
        "min_x": min_x,
        "min_y": min_y,
        "tile_x_count": max_x - min_x + 1,
        "tile_y_count": max_y - min_y + 1,
        "zoom": zoom,
        "image_width": width_px,
        "image_height": height_px
    }
    return stitched, meta

def latlon_to_pixel_in_stitched(lat, lon, meta):
    z = meta["zoom"]
    t = mercantile.tile(lon, lat, z)
    b = mercantile.bounds(t.x, t.y, z)
    if (b.east - b.west) == 0 or (b.north - b.south) == 0:
        x_in_tile = 0
        y_in_tile = 0
    else:
        x_in_tile = (lon - b.west) / (b.east - b.west) * TILE_SIZE
        y_in_tile = (b.north - lat) / (b.north - b.south) * TILE_SIZE
    px = (t.x - meta["min_x"]) * TILE_SIZE + int(round(x_in_tile))
    py = (t.y - meta["min_y"]) * TILE_SIZE + int(round(y_in_tile))
    return px, py

def convert_to_bottom_left_coordinates(pixel_coords, image_height):
    """Convert pixel coordinates to have bottom-left as origin (0,0)"""
    converted = []
    for px, py in pixel_coords:
        # Invert y-coordinate: y_new = image_height - y_old
        converted.append((px, image_height - py))
    return converted

# -----------------------------
# Flask routes
# -----------------------------
@app.route("/")
def index():
    template = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Map Annotator - Flask</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.3/dist/leaflet.css"/>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"/>
  <style>
    html,body,#map { height:100%; margin:0; padding:0; }
    .sidebar {
      position: absolute;
      z-index: 1000;
      right: 10px;
      top: 10px;
      width: 340px;
      max-height: 90%;
      overflow:auto;
      background: rgba(255,255,255,0.96);
      padding:10px;
      border-radius:8px;
      box-shadow:0 2px 12px rgba(0,0,0,0.35);
      font-family: Arial, Helvetica, sans-serif;
      font-size:13px;
    }
    .sidebar h3{margin:0 0 6px 0}
    table{width:100%; border-collapse:collapse}
    td,th{padding:4px; border-bottom:1px solid #eee}
    .btn{padding:6px 8px;background:#007bff;color:white;border-radius:4px;border:none;cursor:pointer}
    .btn-danger{background:#d9534f}
    .btn-zoom{background:#28a745}
    .small{font-size:12px;color:#555}
  </style>
</head>
<body>
<div id="map"></div>
<div class="sidebar">
  <h3>Annotations</h3>
  <input id="searchbox" placeholder="Search place (Nominatim)" style="width:66%"/>
  <button id="searchBtn" class="btn">Search</button>
  <hr/>
  <div>
    <label>Tile server:</label>
    <select id="tileServer">
      <option value="ESRI World Imagery">ESRI World Imagery</option>
      <option value="Google Satellite">Google Satellite</option>
      <option value="Google Hybrid">Google Hybrid</option>
      <option value="Google Roads">Google Roads</option>
      <option value="Google Terrain">Google Terrain</option>
      <option value="OpenStreetMap">OpenStreetMap</option>
      <option value="OpenTopoMap">OpenTopoMap</option>
      <option value="CartoDB Dark">CartoDB Dark</option>
      <option value="CartoDB Light">CartoDB Light</option>
    </select>
  </div>
  <hr/>
  <div id="listArea" style="font-size:12px">
    <table id="polyTable">
      <thead><tr><th>S.No</th><th>Name</th><th>Category</th><th>View</th><th>Zoom</th><th>Del</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
  <hr/>
  <div class="small">Draw a polygon on the map and click Save. Can zoom visually past tile limit (tiles are scaled locally).</div>
</div>

<script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>

<script>
  const CAT_COLORS = {
    "rooftop": '#e6194b',
    "rooftop free": '#3cb44b', 
    "rooftop obs": '#ffe119',
    "street": '#4363d8',
    "ground": '#f58231',
    "PV": '#911eb4',
    "water": '#42d4f4',
    "trees": '#bfef45',
    "grass": '#fabed4'
  };

  const CATEGORIES = {{ categories|tojson }};

  const map = L.map('map', { maxZoom: 25, zoomSnap: 0.25, wheelPxPerZoomLevel: 120 }).setView([24.8607, 67.0011], 12);

  const tileServers = {
      "ESRI World Imagery": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      "Google Satellite": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
      "Google Hybrid": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
      "Google Roads": "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
      "Google Terrain": "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
      "OpenStreetMap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      "OpenTopoMap": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
      "CartoDB Dark": "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      "CartoDB Light": "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
  };

let currentTileLayer = L.tileLayer(tileServers['ESRI World Imagery'], { maxNativeZoom: 19, maxZoom: 25 }).addTo(map);

  document.getElementById('tileServer').addEventListener('change', (e)=>{
    map.removeLayer(currentTileLayer);
    currentTileLayer = L.tileLayer(tileServers[e.target.value], { maxNativeZoom: 19, maxZoom: 25 }).addTo(map);
  });

  const drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);

  const drawControl = new L.Control.Draw({
    draw: {
      polyline: false, rectangle: false, circle: false, marker:false, circlemarker:false,
      polygon: { allowIntersection: false, showArea: true }
    },
    edit: { featureGroup: drawnItems }
  });
  map.addControl(drawControl);

  // Keep map-side reference to server polygons
  let serverPolygons = {}; // id -> layer

  function clearServerPolygons() {
    Object.keys(serverPolygons).forEach(k=>{
      try { if (map.hasLayer(serverPolygons[k])) map.removeLayer(serverPolygons[k]); } catch(e){}
    });
    serverPolygons = {};
  }

  function refreshList(){
    fetch('/list_polygons').then(r=>r.json()).then(data=>{
      const tbody = document.querySelector('#polyTable tbody');
      tbody.innerHTML = '';

      // remove old polygons before re-draw to prevent stacking
      clearServerPolygons();

      data.forEach((p, idx)=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${idx+1}</td>
          <td title="${p.name_short}">${p.name_short}</td>
          <td><select data-id="${p.id}" class="catSel">
            ${CATEGORIES.map(cat => 
              `<option value="${cat.name}"${p.category===cat.name?' selected':''}>${cat.name}</option>`
            ).join('')}
          </select></td>
          <td style="text-align:center"><input type="checkbox" data-id="${p.id}" class="visChk" ${p.visible ? 'checked' : ''}/></td>
          <td style="text-align:center"><button class="btn-zoom btn" data-id="${p.id}">🔍</button></td>
          <td><button class="btn btn-danger" data-id="${p.id}">Delete</button></td>`;
        tbody.appendChild(tr);

        const coords = p.coordinates.map(pt => [pt[1], pt[0]]);
        const poly = L.polygon(coords, {color: CAT_COLORS[p.category] || '#000', weight:2}).addTo(map);
        serverPolygons[p.id] = poly;
        if(!p.visible){
          try{ map.removeLayer(poly); }catch(e){}
        }
      });

      // category change
      document.querySelectorAll('.catSel').forEach(el=>{
        el.addEventListener('change', ev=>{
          const id = ev.target.dataset.id;
          const category = ev.target.value;
          fetch('/update_category', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id, category})})
            .then(()=>refreshList()).catch(e=>console.error(e));
        });
      });

      // visibility toggle - remove/add layer immediately
      document.querySelectorAll('.visChk').forEach(el=>{
        el.addEventListener('change', ev=>{
          const id = ev.target.dataset.id;
          const show = ev.target.checked;
          // immediate UI change:
          if (serverPolygons[id]) {
            if (show) {
              map.addLayer(serverPolygons[id]);
            } else {
              try { map.removeLayer(serverPolygons[id]); } catch(e){}
            }
          }
          fetch('/set_visibility', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id, visible:show})})
            .then(()=>{/* optional: refreshList(); */})
            .catch(e=>console.error(e));
        });
      });

      // zoom highlight functionality
      document.querySelectorAll('.btn-zoom').forEach(el=>{
        el.addEventListener('click', ev=>{
          const id = ev.target.dataset.id;
          const polyLayer = serverPolygons[id];
          if(!polyLayer){
            // fallback: refetch server and refresh
            refreshList();
            return;
          }
          // Ensure visible
          if(!map.hasLayer(polyLayer)){
            map.addLayer(polyLayer);
            // also update server-side visible flag
            fetch('/set_visibility', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id, visible:true})})
              .catch(e=>console.error(e));
          }
          // bold the outline (temporarily) then revert
          const originalStyle = { color: polyLayer.options.color, weight: polyLayer.options.weight || 2 };
          try {
            polyLayer.setStyle({ weight: 6 });
          } catch(e){}
          // zoom to bounds
          try {
            const bounds = polyLayer.getBounds();
            map.fitBounds(bounds.pad(0.12), { maxZoom: 20 });
          } catch(e){}
          // revert after 2000 ms
          setTimeout(()=>{
            try { polyLayer.setStyle({ weight: originalStyle.weight, color: originalStyle.color }); } catch(e){}
          }, 2000);
        });
      });

      // delete - remove layer immediately and call server
      document.querySelectorAll('.btn-danger').forEach(el=>{
        el.addEventListener('click', ev=>{
          const id = ev.target.dataset.id;
          if(!confirm('Delete this polygon?')) return;
          // remove immediately from map
          if (serverPolygons[id]) {
            try { map.removeLayer(serverPolygons[id]); } catch(e){}
            delete serverPolygons[id];
          }
          fetch('/delete_polygon', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})})
            .then(()=>refreshList()).catch(e=>console.error(e));
        });
      });

    }).catch(e=>{
      console.error("Failed to list polygons", e);
    });
  }
  refreshList();

  map.on(L.Draw.Event.CREATED, function (e) {
    const layer = e.layer;
    drawnItems.addLayer(layer);
    const latlngs = layer.getLatLngs()[0];
    const coords = latlngs.map(ll => [ll.lng, ll.lat]);
    const center = layer.getBounds().getCenter();
    const popup = L.popup()
      .setLatLng(center)
      .setContent(`<div>
        <div><strong>Save polygon</strong></div>
        <div>Short name: <input id="pname" value="p_${new Date().toISOString().slice(0,19)}" style="width:160px"/></div>
        <div>Category:
          <select id="pcat">
            ${CATEGORIES.map(cat => `<option value="${cat.name}">${cat.name}</option>`).join('')}
          </select>
        </div>
        <div style="margin-top:6px"><button id="saveBtn" class="btn">Save polygon</button></div>
      </div>`);
    popup.openOn(map);

    setTimeout(()=> {
      document.getElementById('saveBtn').onclick = function(){
        const shortname_raw = document.getElementById('pname').value || ('p_'+Date.now());
        // sanitize client-side too (avoid sending colons)
        const shortname = shortname_raw.replace(/[\\\/:\*\?"\<\>\|]/g, '_');
        const category = document.getElementById('pcat').value;
        const tileServer = document.getElementById('tileServer').value;
        fetch('/save_polygon', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({coordinates: coords, name_short: shortname, category:category, tile_server:tileServer})
        }).then(r=>{
          if(!r.ok) return r.json().then(j=>{ throw new Error(j.message || j.status || ('HTTP ' + r.status)); });
          return r.json();
        }).then(resp=>{
          // smooth flow: no blocking alerts
          try { drawnItems.clearLayers(); } catch(e){}
          map.closePopup();
          refreshList();
        }).catch(err=>{
          alert('Save failed: ' + err.message);
          console.error("Save error:", err);
        });
      };
    }, 200);
  });

  document.getElementById('searchBtn').addEventListener('click', ()=>{
    const q = document.getElementById('searchbox').value;
    if(!q) return;
    fetch('/geocode?q=' + encodeURIComponent(q)).then(r=>r.json()).then(d=>{
      if(d && d.lat && d.lon){
        map.setView([d.lat, d.lon], 17);
      } else {
        alert('Not found');
      }
    }).catch(e=>console.error(e));
  });
</script>
</body>
</html>
    """
    return render_template_string(template, 
                                TILE_SERVERS=TILE_SERVERS,
                                categories=CATEGORIES)

@app.route("/geocode")
def geocode():
    q = request.args.get("q","")
    if not q:
        return jsonify({})
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", params={"q":q,"format":"json","limit":1}, headers=HEADERS, timeout=10)
        j = r.json()
        if not j:
            return jsonify({})
        return jsonify({"lat": float(j[0]["lat"]), "lon": float(j[0]["lon"]), "display_name": j[0].get("display_name","")})
    except Exception as e:
        print("[GEOCODE ERROR]", e)
        return jsonify({})

@app.route("/save_polygon", methods=["POST"])
def save_polygon():
    try:
        data = request.get_json()
        coords = data.get("coordinates")
        name_short = data.get("name_short", f"p_{timestamp_str()}")
        # sanitize name for filesystem
        for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
            name_short = name_short.replace(ch, '_')

        category = data.get("category", "rooftop")
        tile_server_key = data.get("tile_server", "ESRI World Imagery")
        tile_server_url = TILE_SERVERS.get(tile_server_key, TILE_SERVERS["ESRI World Imagery"])

        if not coords or len(coords) < 3:
            return jsonify({"status": "invalid polygon", "message":"polygon must have at least 3 points"}), 400

        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        chosen_zoom = 19
        for z in range(19, 11, -1):
            try:
                tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, z))
                if tiles and len(tiles) <= 400:
                    chosen_zoom = z
                    break
            except Exception as e:
                print("[zoom choose error]", e)

        stitched_img, meta = stitch_tiles_for_bounds(min_lon, min_lat, max_lon, max_lat, chosen_zoom, tile_server_url)

        os.makedirs(CAPTURE_DIR, exist_ok=True)

        ts = timestamp_str()
        fname = f"{ts}_{name_short}_z{chosen_zoom}.png"
        fpath = os.path.join(CAPTURE_DIR, fname)
        stitched_img.save(fpath, "PNG")

        # Convert polygon coordinates (lat/lon) to pixel coordinates in stitched image
        poly_pixels = [latlon_to_pixel_in_stitched(lat, lon, meta) for lon, lat in coords]
        
        # Convert to bottom-left origin coordinates
        poly_pixels_bottom_left = convert_to_bottom_left_coordinates(poly_pixels, stitched_img.height)

        # Prepare JSON data with all information
        json_data = {
            "name_short": name_short,
            "timestamp": ts,
            "category": category,
            "coordinates_latlon": coords,  # Original lat/lon coordinates
            "coordinates_pixels": poly_pixels,  # Pixel coordinates with top-left origin
            "coordinates_pixels_bottom_left": poly_pixels_bottom_left,  # Pixel coordinates with bottom-left origin
            "image_metadata": {
                "width": stitched_img.width,
                "height": stitched_img.height,
                "zoom": chosen_zoom,
                "tile_server": tile_server_key,
                "min_lon": min_lon,
                "max_lon": max_lon,
                "min_lat": min_lat,
                "max_lat": max_lat
            }
        }

        json_name = f"{ts}_{name_short}.json"
        json_path = os.path.join(CAPTURE_DIR, json_name)
        with open(json_path, "w") as jf:
            json.dump(json_data, jf, indent=2)

        db = load_db()
        entry_id = f"{ts}_{name_short}"
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        db.append({
            "id": entry_id,
            "name_short": name_short,
            "timestamp": ts,
            "category": category,
            "coordinates": coords,
            "json_path": json_path,
            "image_path": f"/captures/{fname}",
            "visible": True,
            "center": [center_lat, center_lon],
            "zoom_used": chosen_zoom
        })
        save_db(db)

        print(f"[SUCCESS] Polygon {name_short} saved -> {fpath}", flush=True)
        return jsonify({"status": "saved", "id": entry_id, "image": f"/captures/{fname}"})
    except Exception as e:
        print("[ERROR in save_polygon]", e)
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/list_polygons")
def list_polygons():
    db = load_db()
    payload = []
    for p in db:
        payload.append({
            "id": p["id"],
            "name_short": p.get("name_short", p["id"]),
            "category": p.get("category", "rooftop"),
            "coordinates": p.get("coordinates", []),
            "visible": p.get("visible", True)
        })
    return jsonify(payload)

@app.route("/delete_polygon", methods=["POST"])
def delete_polygon():
    data = request.get_json()
    pid = data.get("id")
    db = load_db()
    newdb = [p for p in db if p["id"] != pid]
    for p in db:
        if p["id"] == pid:
            try:
                if p.get("json_path") and os.path.exists(p["json_path"]): 
                    os.remove(p["json_path"])
                if p.get("image_path"):
                    ip = p["image_path"].lstrip("/")
                    ipath = os.path.join(os.getcwd(), ip)
                    if os.path.exists(ipath): 
                        os.remove(ipath)
            except Exception as e:
                print("[delete file error]", e)
    save_db(newdb)
    return jsonify({"status":"deleted"})

@app.route("/update_category", methods=["POST"])
def update_category():
    data = request.get_json()
    pid = data.get("id")
    category = data.get("category", "rooftop")
    db = load_db()
    for p in db:
        if p["id"] == pid:
            p["category"] = category
            # update polygon JSON file if present
            try:
                jp = p.get("json_path")
                if jp and os.path.exists(jp):
                    with open(jp, "r", encoding="utf-8") as jf:
                        jdata = json.load(jf)
                    jdata["category"] = category
                    with open(jp, "w", encoding="utf-8") as jf:
                        json.dump(jdata, jf, indent=2)
            except Exception as e:
                print("[update_category json write error]", e)
            break
    save_db(db)
    return jsonify({"status":"ok"})

@app.route("/set_visibility", methods=["POST"])
def set_visibility():
    data = request.get_json()
    pid = data.get("id")
    vis = bool(data.get("visible", True))
    db = load_db()
    for p in db:
        if p["id"] == pid:
            p["visible"] = vis
            break
    save_db(db)
    return jsonify({"status":"ok"})

@app.route("/captures/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(CAPTURE_DIR, filename)

if __name__ == "__main__":
    # run without reloader so exceptions are more deterministic in terminal
    app.run(debug=True, use_reloader=False)