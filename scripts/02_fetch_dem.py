"""Download Copernicus DEM GLO-30 tile(s) covering the AOI and clip to it.

The Copernicus DEM GLO-30 public bucket needs no credentials. Tiles are 1x1 degree,
named like Copernicus_DSM_COG_10_N45_00_E012_00_DEM.tif (30 m resolution).
"""
import math

import rasterio
import rasterio.merge
import requests
from rasterio.mask import mask
from shapely.geometry import box, mapping

from config import AOI_BBOX, COPERNICUS_DEM_S3, DATA_RAW

OUT_DIR = DATA_RAW / "dem"
CLIPPED_OUT = OUT_DIR / "venice_dem_clip.tif"


def tile_name(lat, lon):
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    lat_i = math.floor(abs(lat))
    lon_i = math.floor(abs(lon))
    return f"Copernicus_DSM_COG_10_{ns}{lat_i:02d}_00_{ew}{lon_i:03d}_00_DEM"


def download_tile(lat, lon):
    name = tile_name(lat, lon)
    url = f"{COPERNICUS_DEM_S3}/{name}/{name}.tif"
    out_path = OUT_DIR / f"{name}.tif"
    if out_path.exists():
        print(f"Already have {out_path.name}")
        return out_path

    print(f"Downloading {url} ...")
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    print(f"Saved -> {out_path}")
    return out_path


def main():
    minx, miny, maxx, maxy = AOI_BBOX
    # collect every 1-degree tile the AOI touches
    lats = {math.floor(miny), math.floor(maxy)}
    lons = {math.floor(minx), math.floor(maxx)}

    tile_paths = [download_tile(lat, lon) for lat in lats for lon in lons]

    aoi_geom = [mapping(box(minx, miny, maxx, maxy))]

    if len(tile_paths) == 1:
        src_path = tile_paths[0]
        with rasterio.open(src_path) as src:
            out_image, out_transform = mask(src, aoi_geom, crop=True)
            out_meta = src.meta.copy()
    else:
        srcs = [rasterio.open(p) for p in tile_paths]
        mosaic, out_transform = rasterio.merge.merge(srcs)
        out_meta = srcs[0].meta.copy()
        out_meta.update({"height": mosaic.shape[1], "width": mosaic.shape[2], "transform": out_transform})
        merged_path = OUT_DIR / "_mosaic.tif"
        with rasterio.open(merged_path, "w", **out_meta) as dst:
            dst.write(mosaic)
        with rasterio.open(merged_path) as src:
            out_image, out_transform = mask(src, aoi_geom, crop=True)
            out_meta = src.meta.copy()

    out_meta.update({"height": out_image.shape[1], "width": out_image.shape[2], "transform": out_transform})
    with rasterio.open(CLIPPED_OUT, "w", **out_meta) as dst:
        dst.write(out_image)

    print(f"Clipped DEM -> {CLIPPED_OUT}")


if __name__ == "__main__":
    main()
