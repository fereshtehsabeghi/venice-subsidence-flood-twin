"""Combine DEM elevation + EGMS subsidence + tide scenarios into a per-building,
per-year, per-scenario flood table ready for Kepler.gl.

Flood depth for a building at year Y under tide scenario S:
    future_ground_elev = dem_elev_now - (subsidence_mm_per_year / 1000) * Y
    flood_depth         = tide_level(S) - future_ground_elev
    is_flooded          = flood_depth > 0
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from scipy.interpolate import griddata

from config import AOI_BBOX, CRS_EGMS, CRS_METRIC, CRS_WGS84, DATA_PROCESSED, DATA_RAW

BUILDINGS_PATH = DATA_RAW / "osm" / "venice_buildings.gpkg"
DEM_PATH = DATA_RAW / "dem" / "venice_dem_clip.tif"
EGMS_DIR = DATA_RAW / "egms"
SCENARIOS_PATH = DATA_RAW / "tide" / "flood_scenarios.json"

OUT_PATH = DATA_PROCESSED / "venice_flood_model.geojson"

YEARS = [0, 10, 20, 30, 50, 100]

# Default building height when OSM has no height/levels tag (meters)
DEFAULT_HEIGHT = 9.0


def load_buildings():
    gdf = gpd.read_file(BUILDINGS_PATH)
    gdf["height_m"] = DEFAULT_HEIGHT
    return gdf


def sample_ground_elevation(dem_path, points_gdf_wgs84, filter_window=9):
    """Sample bare-ground elevation near each point from the Copernicus DEM.

    Copernicus DEM GLO-30 is a *surface* model (DSM): at a building's own footprint
    it measures the rooftop / radar return off the structure, not the ground beneath
    it — sampling it directly at building centroids gave Venice buildings elevations
    up to 24m in a lagoon city that sits ~0.9m above sea level on average. A local
    minimum filter approximates bare ground by taking the lowest nearby pixel
    (typically a street, canal, or campo) within a small window before sampling,
    which is the standard cheap DSM-to-DTM approximation when a true bare-earth
    model isn't available for free.
    """
    from rasterio.transform import rowcol
    from scipy.ndimage import minimum_filter

    with rasterio.open(dem_path) as src:
        arr = src.read(1)
        transform = src.transform

    ground = minimum_filter(arr, size=filter_window)

    values = []
    for geom in points_gdf_wgs84:
        row, col = rowcol(transform, geom.x, geom.y)
        row = min(max(row, 0), ground.shape[0] - 1)
        col = min(max(col, 0), ground.shape[1] - 1)
        values.append(ground[row, col])
    return np.array(values, dtype=float)


def load_egms_velocity():
    """Load EGMS L3 vertical-motion points (raw CLMS CSVs) if available.

    EGMS CSVs use `easting`/`northing` in EPSG:3035 (ETRS89-LAEA), not lon/lat, and
    each 100km tile file can be 100s of MB with 250+ per-epoch columns, so we stream
    it in chunks, keep only points inside the AOI, and reproject those to WGS84.

    Returns a DataFrame with columns lon, lat, mean_velocity (mm/year, negative = subsiding).
    Falls back to None if no EGMS data has been downloaded yet.
    """
    csvs = list(EGMS_DIR.glob("*.csv"))
    if not csvs:
        print("WARNING: no EGMS data found in data/raw/egms — run 04_fetch_egms.py first.")
        print("Falling back to a flat -2.5 mm/year subsidence estimate for the whole AOI")
        print("(the literature range for Venice lagoon subsidence).")
        return None

    to_egms = Transformer.from_crs(CRS_WGS84, CRS_EGMS, always_xy=True)
    to_wgs84 = Transformer.from_crs(CRS_EGMS, CRS_WGS84, always_xy=True)
    minx, miny, maxx, maxy = AOI_BBOX
    e0, n0 = to_egms.transform(minx, miny)
    e1, n1 = to_egms.transform(maxx, maxy)
    e_min, e_max = sorted((e0, e1))
    n_min, n_max = sorted((n0, n1))

    frames = []
    for csv_path in csvs:
        print(f"Scanning {csv_path.name} for points inside the AOI ...")
        for chunk in pd.read_csv(csv_path, usecols=["pid", "easting", "northing", "mean_velocity"], chunksize=200_000):
            sub = chunk[chunk.easting.between(e_min, e_max) & chunk.northing.between(n_min, n_max)]
            if len(sub):
                frames.append(sub)

    if not frames:
        print("WARNING: EGMS files downloaded but none of their points fall inside the AOI.")
        return None

    df = pd.concat(frames, ignore_index=True)
    lon, lat = to_wgs84.transform(df["easting"].to_numpy(), df["northing"].to_numpy())
    df["lon"] = lon
    df["lat"] = lat
    print(f"Loaded {len(df)} EGMS InSAR points inside the AOI.")
    return df[["lon", "lat", "mean_velocity"]]


def interpolate_subsidence(buildings_wgs84, egms_points):
    if egms_points is None or len(egms_points) < 4:
        return np.full(len(buildings_wgs84), -2.5)

    xy = egms_points[["lon", "lat"]].to_numpy()
    values = egms_points["mean_velocity"].to_numpy()
    query_xy = np.array([(g.x, g.y) for g in buildings_wgs84])

    interpolated = griddata(xy, values, query_xy, method="linear")
    nearest = griddata(xy, values, query_xy, method="nearest")
    interpolated = np.where(np.isnan(interpolated), nearest, interpolated)
    return interpolated


def main():
    buildings = load_buildings()
    buildings_wgs84 = buildings.to_crs(CRS_WGS84)
    centroids_wgs84 = buildings.to_crs(CRS_METRIC).geometry.centroid.to_crs(CRS_WGS84)

    print("Sampling ground elevation (DSM minimum-filtered to approximate bare earth) ...")
    elevations = sample_ground_elevation(DEM_PATH, centroids_wgs84)

    print("Loading/interpolating EGMS subsidence velocity ...")
    egms_points = load_egms_velocity()
    velocity_mm_yr = interpolate_subsidence(centroids_wgs84, egms_points)

    scenarios = json.load(open(SCENARIOS_PATH))

    # One geometry per building. Future ground elevation only depends on `year`
    # (not on tide scenario), so store one compact column per year and let the
    # viewer compute flood_depth = tide_level[scenario] - ge_<year> client-side.
    # This avoids duplicating every building polygon once per year x scenario.
    out = buildings[["osmid", "height_m", "geometry"]].copy()
    out["ground_elev_now_m"] = elevations.round(3)
    for year in YEARS:
        subsidence_m = -(velocity_mm_yr / 1000.0) * year  # velocity is negative when subsiding
        future_elev = elevations - subsidence_m
        out[f"ge_{year}"] = future_elev.round(3)

    out_gdf = gpd.GeoDataFrame(out, geometry="geometry", crs=buildings.crs).to_crs(CRS_WGS84)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_gdf.to_file(OUT_PATH, driver="GeoJSON")

    scenarios_out = DATA_PROCESSED / "flood_scenarios.json"
    with open(scenarios_out, "w", encoding="utf-8") as f:
        json.dump({"years": YEARS, "scenarios": scenarios}, f, indent=2)

    print(f"Wrote {len(out_gdf)} buildings x {len(YEARS)} year-columns -> {OUT_PATH}")
    print(f"Wrote years/scenarios lookup -> {scenarios_out}")


if __name__ == "__main__":
    main()
