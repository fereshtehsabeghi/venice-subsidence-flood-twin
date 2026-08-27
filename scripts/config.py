"""Shared config for the Venice digital twin pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

# Venice historic center + a fringe of the lagoon, in WGS84 (minx, miny, maxx, maxy)
AOI_BBOX = (12.28, 45.40, 12.38, 45.47)

CRS_WGS84 = "EPSG:4326"
CRS_METRIC = "EPSG:32633"  # UTM 33N, meters — used for area/height math
CRS_EGMS = "EPSG:3035"  # ETRS89-LAEA Europe, meters — native CRS of EGMS easting/northing

TIDE_ENDPOINTS = {
    "livello": "http://dati.venezia.it/sites/default/files/dataset/opendata/livello.json",
    "previsione": "http://dati.venezia.it/sites/default/files/dataset/opendata/previsione.json",
}

# Copernicus DEM GLO-30 public AWS bucket (no auth required)
COPERNICUS_DEM_S3 = "https://copernicus-dem-30m.s3.amazonaws.com"
