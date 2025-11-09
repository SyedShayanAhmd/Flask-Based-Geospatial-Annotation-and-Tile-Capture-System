# Flask-Based-Geospatial-Annotation-and-Tile-Capture-System
This project is a complete Flask web application designed for creating, managing, and storing geospatial polygon annotations directly on interactive maps. 
Key Features:

🌍 Multi-Tile Map Integration
Supports a range of base maps including ESRI World Imagery, Google Satellite, Google Hybrid, OpenStreetMap, and CartoDB styles. The user can switch between them dynamically through the web interface.

🧭 Interactive Annotation Tool
Built using Leaflet.js and Leaflet Draw, allowing users to draw, edit, or delete polygons directly on the map. Each annotation can be assigned a custom category (e.g., rooftop, PV, street, water, etc.).

📸 Automated Tile Capture
When a polygon is saved, the backend automatically downloads all satellite tiles within the polygon’s bounding box, stitches them into a single high-resolution image, and stores it locally along with metadata.

📁 Structured Data Management
Each annotation is saved as a JSON file containing:

Latitude/longitude coordinates

Pixel coordinates in the stitched image (both top-left and bottom-left origin systems)

Tile server info, zoom level, and image resolution

Category and timestamp

A central polygons_db.json maintains a registry of all saved annotations.

🔍 Built-in Geocoding and Search
Uses Nominatim (OpenStreetMap API) to locate places by name, instantly centering the map on the searched location.

🧱 Sidebar Polygon Manager
Includes a live sidebar table showing all saved polygons with options to:

Change visibility

Update category

Zoom to the polygon

Delete entries

🖥️ Auto Setup Script (.bat)
A batch script automates setup:

Checks for Python installation

Creates a virtual environment

Installs dependencies (Flask, Folium, Mercantile, Pillow, etc.)

Launches the app and opens it in a browser

This makes deployment seamless even for non-technical users.

Use Cases

Solar rooftop mapping

Environmental annotation and land classification

Dataset generation for ML model training

GIS-based surveying projects

UAV image validation and remote sensing

Tech Stack

Frontend: Leaflet.js, HTML5, CSS

Backend: Flask (Python)

Dependencies: Pillow, Mercantile, Requests, PyProj

Automation: Batch scripting for setup

This project showcases a strong integration of geospatial data handling, web interactivity, and backend automation, providing a user-friendly yet technically robust environment for geospatial annotation and data extraction.

📘 README.md
# Flask Map Annotator & Tile Capture Tool 🗺️  
### Developed by **Syed Shayan Ahmed**

---

## 🚀 Overview
This Flask web app allows users to annotate polygons on a map, automatically capture satellite tiles, and save annotated data (image + coordinates) for geospatial analysis.

It includes a **Windows auto-setup script** (`run_app.bat`) that installs dependencies, creates a virtual environment, and launches the app instantly.

---

## 🧩 Features
- 🌐 Switch between multiple map tile servers (Google, ESRI, OSM, etc.)
- ✏️ Draw and save polygons directly on the map
- 🏷️ Categorize polygons (rooftop, PV, trees, water, etc.)
- 🗺️ Automatically download and stitch map tiles for selected areas
- 🧮 Save both geographic and pixel coordinates
- 🔍 Search places using OpenStreetMap’s Nominatim API
- 🧱 Manage polygons (view, hide, zoom, delete) in the sidebar
- 🧠 JSON database for all saved annotations
- 🖥️ One-click auto setup via `.bat` file

---

## ⚙️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/flask-map-annotator.git
cd flask-map-annotator

2. Run the auto-setup script

Simply double-click:

run_app.bat


This will:

Check for Python

Create a virtual environment

Install all required libraries

Start the Flask server

Open the app in your browser

🧰 Manual Setup (Optional)

If you prefer manual setup:

python -m venv venv
venv\Scripts\activate
pip install flask folium pyproj pillow mercantile requests
python app.py


Then open your browser at:
👉 http://127.0.0.1:5000/

📁 File Structure
├── app.py                # Main Flask application
├── run_app.bat           # Auto setup & launcher script
├── polygons_db.json      # Polygon registry (auto-created)
├── captures/             # Stores stitched images & JSON data

💡 Usage

Draw a polygon on the map.

Enter a name and category.

Click Save Polygon.

The app downloads tiles, saves an image, and creates a JSON metadata file.

Manage all annotations in the sidebar table.

🧠 Tech Stack

Frontend: Leaflet.js, HTML, CSS

Backend: Flask (Python)

Libraries: Pillow, Requests, Mercantile, PyProj

🧾 License

This project is released under the MIT License.
Feel free to use, modify, and distribute with attribution.
