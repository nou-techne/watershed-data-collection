"""
fetch_snowpack.py
Pulls Snow Water Equivalent (SWE) and precipitation data from
NRCS SNOTEL stations in the Colorado River Basin headwaters.

Filters by HUC-2: 14 (Upper Colorado) and 15 (Lower Colorado).
No API key required. Free public data.
Docs: https://wcc.sc.egov.usda.gov/awdbRestApi/swagger-ui/index.html
"""

import requests
from datetime import date, timedelta

AWDB_BASE = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1"

# Colorado River Basin headwater states (Upper Basin)
BASIN_STATES = ["CO", "UT", "WY", "NM", "AZ", "NV"]

# HUC-2 prefixes for Colorado River Basin
COLORADO_RIVER_HUCS = {"14", "15"}

# SNOTEL element codes
ELEMENTS = [
    "WTEQ",  # Snow Water Equivalent, inches
    "PREC",  # Accumulated precipitation since Oct 1, inches
    "SNWD",  # Snow depth, inches
    "TOBS",  # Observed temperature, degrees F
]

# Reference normals for percent-of-normal calculation (median SWE for Feb 1 by basin)
# Source: NRCS Basin Outlook Reports — approximate values for context
BASIN_NORMAL_SWE = {
    "Upper Colorado": 14.5,   # inches SWE median
    "Gunnison": 16.2,
    "Yampa/White": 13.8,
    "San Juan": 15.0,
}


def get_colorado_river_stations() -> list[dict]:
    """Fetch all active SNOTEL stations in Colorado River Basin HUCs."""
    resp = requests.get(
        f"{AWDB_BASE}/stations",
        params={"networkCd": "SNTL", "activeInd": "true"},
        timeout=60
    )
    resp.raise_for_status()
    all_stations = resp.json()

    # Filter to Colorado River Basin HUC-2 (14 = Upper Colorado, 15 = Lower Colorado)
    basin_stations = []
    for s in all_stations:
        huc = s.get("huc", "")
        if huc[:2] in COLORADO_RIVER_HUCS and s.get("stateCode") in BASIN_STATES:
            basin_stations.append(s)

    print(f"[snowpack] found {len(basin_stations)} SNOTEL stations in Colorado River Basin")
    return basin_stations


def fetch_station_data(triplets: list[str], element_cd: str, today: str,
                       include_median: bool = False) -> dict:
    """Batch-fetch element data for a list of station triplets.
    If include_median=True, returns {triplet: (value, median)} tuples."""
    params = {
        "stationTriplets": ",".join(triplets),
        "elements": element_cd,
        "beginDate": today,
        "endDate": today,
    }
    if include_median:
        params["centralTendencyType"] = "MEDIAN"

    resp = requests.get(f"{AWDB_BASE}/data", params=params, timeout=120)
    if resp.status_code != 200:
        return {}
    raw = resp.json()
    result = {}
    for entry in raw:
        triplet = entry.get("stationTriplet")
        data_list = entry.get("data", [])
        if data_list and data_list[0].get("values"):
            values = data_list[0]["values"]
            if values:
                val = values[-1].get("value")
                med = values[-1].get("median") if include_median else None
                if val is not None:
                    if include_median:
                        result[triplet] = (float(val), float(med) if med is not None else None)
                    else:
                        result[triplet] = float(val)
    return result


def fetch_snowpack() -> dict:
    """
    Returns aggregated snowpack data:
    - stations: list of individual station readings
    - summary: basin-wide aggregates (mean SWE, count, etc.)
    """
    stations = get_colorado_river_stations()
    if not stations:
        return {"stations": [], "summary": {}}

    # SNOTEL data has 1-day lag - use yesterday's date
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    triplets = [s["stationTriplet"] for s in stations]

    # Batch fetch — smaller chunks for median requests (heavier API load)
    CHUNK = 30
    swe_data, prec_data, snwd_data = {}, {}, {}

    for i in range(0, len(triplets), CHUNK):
        chunk = triplets[i : i + CHUNK]
        try:
            swe_data.update(fetch_station_data(chunk, "WTEQ", yesterday, include_median=True))
        except Exception as e:
            print(f"[snowpack] SWE batch {i} failed: {e}")
        try:
            prec_data.update(fetch_station_data(chunk, "PREC", yesterday))
        except Exception as e:
            print(f"[snowpack] PREC batch {i} failed: {e}")
        try:
            snwd_data.update(fetch_station_data(chunk, "SNWD", yesterday))
        except Exception as e:
            print(f"[snowpack] SNWD batch {i} failed: {e}")

    # Build station records
    station_records = []
    swe_values = []

    pct_values = []

    for s in stations:
        triplet = s["stationTriplet"]
        swe_entry = swe_data.get(triplet)  # (value, median) tuple or None
        prec = prec_data.get(triplet)
        snwd = snwd_data.get(triplet)

        swe = None
        swe_median = None
        pct_of_median = None

        if swe_entry is not None:
            swe, swe_median = swe_entry
            if swe is not None:
                swe_values.append(swe)
            if swe is not None and swe_median and swe_median > 0:
                pct_of_median = round(swe / swe_median * 100, 1)
                pct_values.append(pct_of_median)

        station_records.append({
            "triplet": triplet,
            "name": s.get("name"),
            "state": s.get("stateCode"),
            "elevation_ft": s.get("elevation"),
            "latitude": s.get("latitude"),
            "longitude": s.get("longitude"),
            "huc": s.get("huc"),
            "swe_in": swe,
            "swe_median_in": swe_median,
            "pct_of_median": pct_of_median,
            "precip_in": prec,
            "snow_depth_in": snwd,
            "date": yesterday,
        })

    # Sort by SWE descending
    station_records.sort(key=lambda x: x["swe_in"] or 0, reverse=True)

    # Basin summary
    valid_swe = [v for v in swe_values if v is not None]
    valid_pct = [v for v in pct_values if v is not None]
    summary = {
        "station_count": len(station_records),
        "stations_reporting": len(valid_swe),
        "mean_swe_in": round(sum(valid_swe) / len(valid_swe), 2) if valid_swe else None,
        "max_swe_in": max(valid_swe) if valid_swe else None,
        "min_swe_in": min(valid_swe) if valid_swe else None,
        "mean_pct_of_median": round(sum(valid_pct) / len(valid_pct), 1) if valid_pct else None,
        "date": yesterday,
    }

    print(f"[snowpack] {summary['stations_reporting']} stations reporting | "
          f"mean SWE: {summary['mean_swe_in']} in")

    return {
        "stations": station_records,
        "summary": summary,
    }


if __name__ == "__main__":
    import json
    result = fetch_snowpack()
    print(f"\nSummary: {json.dumps(result['summary'], indent=2)}")
    print(f"\nTop 10 stations by SWE:")
    for s in result["stations"][:10]:
        print(f"  {s['name']:40s} {s['state']}  SWE: {s['swe_in']} in")
