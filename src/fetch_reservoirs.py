"""
fetch_reservoirs.py
Pulls reservoir water surface elevation data from USGS, plus daily
median statistics for percent-of-normal context.

No API key required.
"""

import requests
from datetime import date

# USGS reservoir sites in the Colorado River Basin
# Note: Lake Mead elevation is maintained by BOR, not USGS real-time.
# Future enhancement: integrate BOR RISE API for Lake Mead.
RESERVOIR_SITES = [
    {
        "id": "09379900",
        "name": "Lake Powell (Glen Canyon Dam)",
        "full_pool_ft": 3700.0,
        "dead_pool_ft": 3370.0,
        "notes": "Full pool 3700 ft; dead pool 3370 ft (generators go offline)"
    },
]

IV_URL = "https://waterservices.usgs.gov/nwis/iv/"
STAT_URL = "https://waterservices.usgs.gov/nwis/stat/"
ELEV_PARAM = "62614"  # Lake/reservoir water surface elevation, ft above NGVD29


def fetch_elevation_median() -> dict:
    """Fetch median daily elevation for today's day-of-year.
    Returns {site_id: median_ft}."""
    today = date.today()
    site_ids = ",".join(s["id"] for s in RESERVOIR_SITES)
    resp = requests.get(STAT_URL, params={
        "format": "rdb",
        "sites": site_ids,
        "statReportType": "daily",
        "statTypeCd": "median",
        "parameterCd": ELEV_PARAM,
    }, timeout=30)
    if resp.status_code != 200:
        return {}

    medians = {}
    for line in resp.text.splitlines():
        if line.startswith("#") or line.startswith("5s") or line.startswith("agency"):
            continue
        parts = line.split("\t")
        if len(parts) < 11:
            continue
        site_id, month, day, median_val = parts[1], parts[5], parts[6], parts[10]
        try:
            if int(month) == today.month and int(day) == today.day:
                medians[site_id] = float(median_val)
        except (ValueError, IndexError):
            continue
    return medians


def fetch_reservoirs() -> list[dict]:
    """Fetch latest reservoir elevation readings + median comparison."""
    site_ids = ",".join(s["id"] for s in RESERVOIR_SITES)
    resp = requests.get(IV_URL, params={
        "format": "json",
        "sites": site_ids,
        "parameterCd": ELEV_PARAM,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    medians = fetch_elevation_median()
    site_meta = {s["id"]: s for s in RESERVOIR_SITES}
    results = []

    for ts in data["value"]["timeSeries"]:
        site_code = ts["sourceInfo"]["siteCode"][0]["value"]
        values = ts["values"][0]["value"]
        latest = values[-1] if values else {}
        meta = site_meta.get(site_code, {})

        if not latest.get("value") or latest["value"] == "-999999":
            continue

        elevation_ft = float(latest["value"])
        full_pool = meta.get("full_pool_ft", 0)
        dead_pool = meta.get("dead_pool_ft", 0)
        median_ft = medians.get(site_code)

        if full_pool > dead_pool:
            fill_pct = max(0, min(100,
                (elevation_ft - dead_pool) / (full_pool - dead_pool) * 100))
        else:
            fill_pct = None

        # Percent of median elevation (relative to usable range)
        pct_of_median = None
        if median_ft and median_ft > dead_pool and full_pool > dead_pool:
            current_usable = elevation_ft - dead_pool
            median_usable = median_ft - dead_pool
            if median_usable > 0:
                pct_of_median = round(current_usable / median_usable * 100, 1)

        results.append({
            "site_id": site_code,
            "name": meta.get("name", ts["sourceInfo"]["siteName"]),
            "elevation_ft": elevation_ft,
            "median_elevation_ft": median_ft,
            "full_pool_ft": full_pool,
            "dead_pool_ft": dead_pool,
            "fill_pct": round(fill_pct, 1) if fill_pct is not None else None,
            "pct_of_median": pct_of_median,
            "latitude": ts["sourceInfo"]["geoLocation"]["geogLocation"]["latitude"],
            "longitude": ts["sourceInfo"]["geoLocation"]["geogLocation"]["longitude"],
            "datetime": latest.get("dateTime"),
            "notes": meta.get("notes", ""),
        })

    print(f"[reservoirs] fetched {len(results)} sites")
    return results


if __name__ == "__main__":
    import json
    reservoirs = fetch_reservoirs()
    print(json.dumps(reservoirs, indent=2))
