# Flask Geospatial Annotation & Tile Capture System

### Project Description
A custom **Web-Based GIS Tool** developed using **Python (Flask)** and **Folium**. This application streamlines the creation of geospatial datasets by allowing users to annotate interactive maps and capture image tiles for Machine Learning training (Satellite Imagery Analysis).

### Key Features
* **Interactive Mapping:** Integrated Folium/Leaflet for real-time map navigation.
* **Polygon Annotation:** Users can draw bounding boxes/polygons over satellite imagery.
* **Tile Capture:** Automates the extraction of map tiles (`.png`/`.jpg`) based on coordinates.
* **Data Export:** Saves annotations in standard formats (JSON/GeoJSON) for RCNN/YOLO training.

### Tech Stack
* **Backend:** Python, Flask
* **Frontend:** HTML/CSS, Jinja2
* **Libraries:** Folium, OpenCV, NumPy, Pillow

### How to Run
1.  Clone the repo: `git clone [url]`
2.  Install requirements: `pip install -r requirements.txt`
3.  Run the app: `python app.py`
4.  Open `localhost:5000` in your browser.
