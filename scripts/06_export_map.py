"""Export the flood model as a self-contained interactive deck.gl HTML map.

Two sliders let you scrub "years into the future" (subsidence accumulation) and
pick a tide scenario; buildings extrude and re-color live as flood depth changes.
No local build step — deck.gl loads from a CDN, all data is embedded in the file.
"""
import json

import geopandas as gpd

from config import DATA_PROCESSED, OUTPUTS

IN_PATH = DATA_PROCESSED / "venice_flood_model.geojson"
SCENARIOS_PATH = DATA_PROCESSED / "flood_scenarios.json"
OUT_PATH = OUTPUTS / "venice_digital_twin.html"

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Venice Subsidence &amp; Sea-Level Digital Twin</title>
<script src="https://unpkg.com/deck.gl@8.9.0/dist.min.js"></script>
<script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
<style>
  html, body, #map { margin: 0; height: 100%; width: 100%; background: #0b1d26; font-family: system-ui, sans-serif; }
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
</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <h1>Venice Digital Twin</h1>
  <p>Ground subsidence (EGMS) + tide scenario -> flood depth per building</p>

  <label for="year">Years into the future: <span id="yearVal"></span></label>
  <input type="range" id="year" min="0" max="0" step="1" value="0" />

  <label for="scenario">Tide scenario</label>
  <select id="scenario"></select>

  <div id="stats"></div>
</div>

<script>
const DATA = __DATA_JSON__;
const META = __META_JSON__;   // { years: [...], scenarios: { name: tide_level_m } }

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

function colorForDepth(d) {
  if (d <= 0) return [70, 130, 150, 180];
  if (d < 0.2) return [255, 195, 0, 200];
  if (d < 0.6) return [255, 106, 61, 220];
  return [216, 30, 20, 240];
}

function floodDepth(props, year, tideLevel) {
  const ge = props['ge_' + year];
  return tideLevel - ge;
}

const deckgl = new deck.DeckGL({
  container: 'map',
  mapStyle: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  initialViewState: { longitude: 12.3345, latitude: 45.4371, zoom: 14.2, pitch: 45, bearing: -10 },
  controller: true,
  layers: []
});

function render() {
  const year = years[+yearInput.value];
  const scenario = scenarioSelect.value;
  const tideLevel = META.scenarios[scenario];
  document.getElementById('yearVal').textContent = year + ' yr';

  let flooded = 0;
  const total = DATA.features.length;
  for (const f of DATA.features) {
    const d = floodDepth(f.properties, year, tideLevel);
    f.properties._flood_depth = d;
    if (d > 0) flooded++;
  }
  document.getElementById('stats').innerHTML =
    `Buildings shown: ${total}<br/>Flooded: <b>${flooded}</b> (${total ? (100*flooded/total).toFixed(1) : 0}%)`;

  const layer = new deck.GeoJsonLayer({
    id: 'buildings',
    data: DATA,
    filled: true,
    extruded: true,
    wireframe: true,
    getElevation: f => f.properties.height_m,
    getFillColor: f => colorForDepth(f.properties._flood_depth),
    getLineColor: [20, 30, 35],
    opacity: 0.9,
    pickable: true,
    autoHighlight: true,
    updateTriggers: { getFillColor: [year, scenario] }
  });

  deckgl.setProps({
    layers: [layer],
    getTooltip: ({object}) => object && {
      html: `<b>Flood depth:</b> ${object.properties._flood_depth.toFixed(2)} m<br/>` +
            `<b>Ground elev (future):</b> ${object.properties['ge_' + year].toFixed(2)} m<br/>` +
            `<b>Ground elev (now):</b> ${object.properties.ground_elev_now_m.toFixed(2)} m`
    }
  });
}

yearInput.addEventListener('input', render);
scenarioSelect.addEventListener('change', render);
render();
</script>
</body>
</html>
"""


def main():
    gdf = gpd.read_file(IN_PATH)
    geojson = json.loads(gdf.to_json())
    meta = json.load(open(SCENARIOS_PATH))

    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(geojson))
    html = html.replace("__META_JSON__", json.dumps(meta))
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Saved interactive digital twin -> {OUT_PATH}")


if __name__ == "__main__":
    main()
