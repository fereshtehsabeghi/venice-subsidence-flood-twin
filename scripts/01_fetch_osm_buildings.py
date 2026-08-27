"""Download building footprints for the Venice AOI from OpenStreetMap."""
import geopandas as gpd
import osmnx as ox

from config import AOI_BBOX, DATA_RAW

OUT_PATH = DATA_RAW / "osm" / "venice_buildings.gpkg"


def main():
    minx, miny, maxx, maxy = AOI_BBOX
    print(f"Fetching OSM buildings for bbox {AOI_BBOX} ...")
    # osmnx >=2.0 expects bbox as (west, south, east, north)
    buildings = ox.features_from_bbox(bbox=(minx, miny, maxx, maxy), tags={"building": True})

    buildings = buildings[buildings.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    buildings = buildings.reset_index()[["id", "building", "geometry"]].rename(columns={"id": "osmid"})

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    buildings.to_file(OUT_PATH, driver="GPKG")
    print(f"Saved {len(buildings)} building footprints -> {OUT_PATH}")


if __name__ == "__main__":
    main()
