"""Export the flood model as a self-contained CesiumJS true-3D-globe digital twin.

Unlike the deck.gl version, buildings are placed at real absolute elevation
(base = future ground elevation, top = base + building height), so as the year
slider advances and subsidence accumulates, building bases visibly sink beneath
a fixed water-level plane set by the tide scenario — the actual physical story.

No Cesium ion account/token needed: imagery is OpenStreetMap raster tiles and
terrain is the flat WGS84 ellipsoid (fine here since our own DEM sampling already
gives each building its real elevation).
"""
import json

import geopandas as gpd

from config import AOI_BBOX, DATA_PROCESSED, OUTPUTS

IN_PATH = DATA_PROCESSED / "venice_flood_model.geojson"
SCENARIOS_PATH = DATA_PROCESSED / "flood_scenarios.json"
OUT_PATH = OUTPUTS / "venice_cesium_twin.html"

CESIUM_VERSION = "1.144.0"

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Venice Subsidence &amp; Sea-Level Digital Twin — CesiumJS</title>
<script src="https://unpkg.com/cesium@__CESIUM_VERSION__/Build/Cesium/Cesium.js"></script>
<link href="https://unpkg.com/cesium@__CESIUM_VERSION__/Build/Cesium/Widgets/widgets.css" rel="stylesheet" />
<style>
  html, body, #cesiumContainer { margin: 0; height: 100%; width: 100%; font-family: system-ui, sans-serif; }
  #panel {
    position: absolute; top: 16px; left: 16px; z-index: 1;
    background: rgba(10, 20, 28, 0.85); color: #e8f1f5; padding: 16px 20px;
    border-radius: 10px; width: 300px; box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  }
  #panel h1 { font-size: 15px; margin: 0 0 4px; }
  #panel p { font-size: 12px; color: #9db3bd; margin: 0 0 14px; }
  #panel label { font-size: 12px; display: block; margin-bottom: 4px; }
  #panel select, #panel input[type=range] { width: 100%; margin-bottom: 14px; }
  #yearVal { font-weight: 600; color: #ffc300; }
  #stats { font-size: 12px; line-height: 1.6; border-top: 1px solid #2a3f47; padding-top: 10px; }
  #stats b { color: #ff6a3d; }
  #loading {
    position: absolute; inset: 0; z-index: 2; background: #0b1d26; color: #e8f1f5;
    display: flex; align-items: center; justify-content: center; font-size: 14px;
  }
</style>
</head>
<body>
<div id="cesiumContainer"></div>
<div id="loading">Building the twin — placing __N_BUILDINGS__ buildings ...</div>
<div id="panel">
  <h1>Venice Digital Twin (CesiumJS)</h1>
  <p>Buildings sit at their real elevation; watch bases sink below the water plane as subsidence accumulates.</p>

  <label for="year">Years into the future: <span id="yearVal"></span></label>
  <input type="range" id="year" min="0" max="0" step="1" value="0" />

  <label for="scenario">Tide scenario</label>
  <select id="scenario"></select>

  <div id="stats"></div>
</div>

<script>
Cesium.Ion.defaultAccessToken = undefined;

const DATA = __DATA_JSON__;
const META = __META_JSON__; // { years: [...], scenarios: { name: tide_level_m } }
const AOI = __AOI_JSON__;   // [minx, miny, maxx, maxy]

const viewer = new Cesium.Viewer('cesiumContainer', {
  baseLayerPicker: false,
  geocoder: false,
  homeButton: true,
  sceneModePicker: true,
  navigationHelpButton: false,
  animation: false,
  timeline: false,
  fullscreenButton: true,
  infoBox: true,
  selectionIndicator: true,
  terrainProvider: new Cesium.EllipsoidTerrainProvider(),
  baseLayer: new Cesium.ImageryLayer(new Cesium.UrlTemplateImageryProvider({
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    credit: 'Imagery © OpenStreetMap contributors'
  }))
});
viewer.scene.globe.depthTestAgainstTerrain = true;

function colorForDepth(d) {
  if (d <= 0) return Cesium.Color.fromBytes(70, 130, 150, 220);
  if (d < 0.2) return Cesium.Color.fromBytes(255, 195, 0, 235);
  if (d < 0.6) return Cesium.Color.fromBytes(255, 106, 61, 240);
  return Cesium.Color.fromBytes(216, 30, 20, 250);
}

function ringToFlat(ring) {
  const flat = [];
  for (const [lon, lat] of ring) { flat.push(lon, lat); }
  return flat;
}

function polygonsOf(geometry) {
  if (geometry.type === 'Polygon') return [geometry.coordinates[0]];
  if (geometry.type === 'MultiPolygon') return geometry.coordinates.map(poly => poly[0]);
  return [];
}

const buildingEntities = [];

for (const feature of DATA.features) {
  const props = feature.properties;
  for (const ring of polygonsOf(feature.geometry)) {
    if (ring.length < 3) continue;
    const positions = Cesium.Cartesian3.fromDegreesArray(ringToFlat(ring));
    const entity = viewer.entities.add({
      polygon: {
        hierarchy: positions,
        height: props.ge_0,
        extrudedHeight: props.ge_0 + props.height_m,
        material: colorForDepth(0),
        outline: false,
        perPositionHeight: false
      }
    });
    buildingEntities.push({ entity, props });
  }
}

// Water-level plane: fixed at the scenario's tide elevation, independent of year —
// buildings sink beneath it as subsidence accumulates, which is the physically correct picture.
const waterEntity = viewer.entities.add({
  rectangle: {
    coordinates: Cesium.Rectangle.fromDegrees(AOI[0], AOI[1], AOI[2], AOI[3]),
    material: Cesium.Color.fromBytes(60, 140, 200, 90),
    height: 0
  }
});

document.getElementById('loading').style.display = 'none';

const years = META.years;
const scenarioNames = Object.keys(META.scenarios);

const yearInput = document.getElementById('year');
yearInput.min = 0;
yearInput.max = years.length - 1;
const scenarioSelect = document.getElementById('scenario');
scenarioNames.forEach(s => {
  const opt = document.createElement('option');
  opt.value = s; opt.textContent = `${s.replace(/_/g, ' ')} (${META.scenarios[s].toFixed(2)} m)`;
  scenarioSelect.appendChild(opt);
});
if (scenarioNames.includes('exceptional_2019')) scenarioSelect.value = 'exceptional_2019';

function updateYearLabel() {
  document.getElementById('yearVal').textContent = years[+yearInput.value] + ' yr';
}

function render() {
  const year = years[+yearInput.value];
  const scenario = scenarioSelect.value;
  const tideLevel = META.scenarios[scenario];
  updateYearLabel();

  waterEntity.rectangle.height = tideLevel;

  let flooded = 0;
  for (const { entity, props } of buildingEntities) {
    const ge = props['ge_' + year];
    const depth = tideLevel - ge;
    if (depth > 0) flooded++;
    entity.polygon.height = ge;
    entity.polygon.extrudedHeight = ge + props.height_m;
    entity.polygon.material = colorForDepth(depth);
  }

  const total = buildingEntities.length;
  document.getElementById('stats').innerHTML =
    `Buildings shown: ${total}<br/>Flooded: <b>${flooded}</b> (${total ? (100*flooded/total).toFixed(1) : 0}%)`;
}

yearInput.addEventListener('input', updateYearLabel);
yearInput.addEventListener('change', render);
scenarioSelect.addEventListener('change', render);
render();

// setView is instant and has no dependency on animation frames actually ticking,
// so the camera is guaranteed to end up over Venice even if flyTo's animation
// below never gets to run (e.g. a backgrounded/non-rendering tab).
viewer.camera.setView({
  destination: Cesium.Cartesian3.fromDegrees(12.3345, 45.4371, 6000),
  orientation: { heading: Cesium.Math.toRadians(20), pitch: Cesium.Math.toRadians(-35) }
});

// Purely cosmetic cinematic zoom-in from that starting point, once the scene
// has actually rendered a frame (avoids Cesium's own init-time camera reset
// silently swallowing a flyTo issued immediately at page load).
const removeFlyToListener = viewer.scene.postRender.addEventListener(function () {
  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(12.3345, 45.4371, 1400),
    orientation: { heading: Cesium.Math.toRadians(20), pitch: Cesium.Math.toRadians(-35) },
    duration: 2
  });
  removeFlyToListener();
});
</script>
</body>
</html>
"""


def main():
    gdf = gpd.read_file(IN_PATH)
    geojson = json.loads(gdf.to_json())
    meta = json.load(open(SCENARIOS_PATH))

    html = HTML_TEMPLATE.replace("__CESIUM_VERSION__", CESIUM_VERSION)
    html = html.replace("__N_BUILDINGS__", str(len(gdf)))
    html = html.replace("__DATA_JSON__", json.dumps(geojson))
    html = html.replace("__META_JSON__", json.dumps(meta))
    html = html.replace("__AOI_JSON__", json.dumps(list(AOI_BBOX)))

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"Saved CesiumJS digital twin -> {OUT_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
