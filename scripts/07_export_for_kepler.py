"""Export a Kepler.gl-ready GeoJSON: pre-computed flood_depth per (year, scenario),
long format, simplified geometry, minimal columns — sized to drag-and-drop into
https://kepler.gl/demo without choking the browser.

Kepler.gl can't do the "tide - elevation" math itself (it only colors/filters on
columns that already exist), so this materializes flood_depth_m per row instead
of relying on client-side JS like outputs/venice_digital_twin.html does.
"""
import json

import geopandas as gpd

from config import DATA_PROCESSED, DATA_RAW, OUTPUTS

IN_PATH = DATA_PROCESSED / "venice_flood_model.geojson"
SCENARIOS_PATH = DATA_PROCESSED / "flood_scenarios.json"
OUT_PATH = OUTPUTS / "venice_kepler_import.geojson"

# Fewer timesteps than the full model, purely to keep the Kepler import light —
# pick the years that tell the clearest story: now, mid, and long-horizon.
KEPLER_YEARS = [0, 50, 100]
SIMPLIFY_TOLERANCE_DEG = 0.00002  # ~2m, imperceptible on building footprints


def main():
    gdf = gpd.read_file(IN_PATH)
    meta = json.load(open(SCENARIOS_PATH))
    scenarios = meta["scenarios"]

    gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)

    rows = []
    for year in KEPLER_YEARS:
        ge = gdf[f"ge_{year}"]
        for scenario_name, tide_level in scenarios.items():
            flood_depth = tide_level - ge
            rows.append(
                gpd.GeoDataFrame(
                    {
                        "osmid": gdf["osmid"],
                        "year": year,
                        "scenario": scenario_name,
                        "flood_depth_m": flood_depth.round(2),
                        "height_m": gdf["height_m"],
                        "geometry": gdf.geometry,
                    },
                    crs=gdf.crs,
                )
            )

    out_gdf = gpd.GeoDataFrame(pd_concat_geo(rows), crs=gdf.crs)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    out_gdf.to_file(OUT_PATH, driver="GeoJSON")

    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"Wrote {len(out_gdf)} rows ({len(gdf)} buildings x {len(KEPLER_YEARS)} years x {len(scenarios)} scenarios)")
    print(f"-> {OUT_PATH} ({size_mb:.1f} MB)")


def pd_concat_geo(gdfs):
    import pandas as pd

    return pd.concat(gdfs, ignore_index=True)


if __name__ == "__main__":
    main()
