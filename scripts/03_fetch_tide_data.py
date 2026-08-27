"""Pull live tide level + forecast from the Comune di Venezia open data portal (no auth)."""
import json

import requests

from config import DATA_RAW, TIDE_ENDPOINTS

OUT_DIR = DATA_RAW / "tide"

# Reference flood scenarios (meters above Punta della Salute zero) used later
# by the flood model, calibrated to real recorded events.
SCENARIOS_M = {
    "normal_high_tide": 0.80,
    "moderate_acqua_alta": 1.10,
    "exceptional_2019": 1.87,  # 12 Nov 2019 record flood
}


def fetch(name, url):
    print(f"Fetching {name} from {url} ...")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{name}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved -> {out_path}")
    return data


def main():
    for name, url in TIDE_ENDPOINTS.items():
        try:
            fetch(name, url)
        except requests.RequestException as e:
            print(f"WARNING: could not fetch {name} ({e}). Continuing with static scenarios only.")

    scenarios_path = OUT_DIR / "flood_scenarios.json"
    with open(scenarios_path, "w", encoding="utf-8") as f:
        json.dump(SCENARIOS_M, f, indent=2)
    print(f"Saved reference flood scenarios -> {scenarios_path}")


if __name__ == "__main__":
    main()
