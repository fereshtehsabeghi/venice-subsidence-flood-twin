"""Download EGMS L3 vertical ground-motion data for the Venice AOI.

Requires a free CLMS API token saved as token.jwt in the project root.
Get one at: https://eea.github.io/clms-api-docs/authentication.html

This follows the official workflow from https://github.com/copernicus-land/egms-api
"""
import json
import time
import zipfile
from pathlib import Path

import jwt
import requests

from config import AOI_BBOX, DATA_RAW, ROOT

TOKEN_PATH = ROOT / "token.jwt"
API_ENDPOINT = "https://egms.land.copernicus.eu/insar-api/archive"
OUT_DIR = DATA_RAW / "egms"


def get_access_token():
    service_key = json.load(open(TOKEN_PATH, "rb"))
    private_key = service_key["private_key"].encode("utf-8")
    claim_set = {
        "iss": service_key["client_id"],
        "sub": service_key["user_id"],
        "aud": service_key["token_uri"],
        "iat": int(time.time()) - 60,  # buffer for clock skew against the CLMS server
        "exp": int(time.time() + 3600),
    }
    grant = jwt.encode(claim_set, private_key, algorithm="RS256")
    r = requests.post(
        service_key["token_uri"],
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": grant},
    )
    r.raise_for_status()
    return r.json()["access_token"]


def main():
    if not TOKEN_PATH.exists():
        print(f"ERROR: {TOKEN_PATH} not found.")
        print("Register a free account at https://land.copernicus.eu/en, generate an API token,")
        print(f"and save it as {TOKEN_PATH} before running this script.")
        return

    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    releases = requests.get(f"{API_ENDPOINT}/releases", headers=headers).json()
    latest_release = releases[-1]
    print(f"Available releases: {releases} -> using {latest_release}")

    minx, miny, maxx, maxy = AOI_BBOX
    query = {
        "id": None,
        "bbox": [[minx, miny], [maxx, maxy]],
        "levels": ["L3"],
        "releases": [latest_release],
        "productType": "ORTHO-UP",  # vertical motion component
    }
    r = requests.post(f"{API_ENDPOINT}/search", headers=headers, data=json.dumps(query))
    result = r.json()
    hits = result.get("hits", [])
    print(f"Query returned {len(hits)} tile(s) for release {latest_release}.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for hit in hits:
        filename = hit["filename"]
        link = f"{API_ENDPOINT}/download/{filename}?id={result['id']}"
        out_path = OUT_DIR / filename
        print(f"Downloading {filename} ...")
        resp = requests.get(link, headers=headers, stream=True)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        if out_path.suffix == ".zip":
            with zipfile.ZipFile(out_path) as z:
                z.extractall(OUT_DIR)
        print(f"Saved -> {out_path}")

    if not hits:
        print("No EGMS tiles matched the AOI/release combo — try a different release from the list above.")


if __name__ == "__main__":
    main()
