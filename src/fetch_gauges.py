"""
fetch_gauges.py
Pulls stream gauge data (discharge + gage height) from the USGS Water
Services API, plus daily median statistics for percent-of-normal context.

No API key required. Free public data.
Docs: https://waterservices.usgs.gov/
"""

import requests
from datetime import date

# Key Colorado River Basin USGS gauge sites — upstream → downstream
GAUGE_SITES = [
    {"id": "09070500",  "name": "Colorado River near Dotsero, CO",           "state": "CO"},
    {"id": "09095500",  "name": "Colorado River near Cameo, CO",              "state": "CO"},
    {"id": "09163500",  "name": "Colorado River nr CO-UT state line",         "state": "CO"},
    {"id": "09180000",  "name": "Colorado River near Moab, UT",               "state": "UT"},
    {"id": "09315000",  "name": "Colorado River at Hite Crossing, UT",        "state": "UT"},
    {"id": "09380000",  "name": "Colorado River at Lees Ferry, AZ",           "state": "AZ"},
    {"id": "09402500",  "name": "Colorado River near Grand Canyon, AZ",       "state": "AZ"},
    {"id": "09421500",  "name": "Colorado River below Hoover Dam, AZ-NV",     "state": "NV"},
    # Major tributaries
    {"id": "09306500",  "name": "White River near Watson, UT",                "state": "UT"},
    {"id": "09328500",  "name": "San Rafael River near Green River, UT",      "state": "UT"},
    {"id": "09430500",  "name": "Gila River near Clifton, AZ",                "state": "AZ"},
]

IV_URL = "https://waterservices.usgs.gov/nwis/iv/"
STAT_URL = "https://waterservices.usgs.gov/nwis/stat/"
PARAM_CODES = "00060,00065"  # Discharge (cfs), Gage height (ft)


def fetch_daily_medians() -> dict:
    """Fetch median daily discharge for today's day-of-year for all sites.
    Returns {site_id: median_cfs}. Batches in groups of 10 (API limit)."""
    today = date.today()
    all_ids = [s["id"] for s in GAUGE_SITES]
    medians = {}

    # USGS stats API allows max 10 sites per request
    BATCH = 10
    for i in range(0, len(all_ids), BATCH):
        batch_ids = ",".join(all_ids[i : i + BATCH])
        resp = requests.get(STAT_URL, params={
            "format": "rdb",
            "sites": batch_ids,
            "statReportType": "daily",
            "statTypeCd": "median",
            "parameterCd": "00060",
        }, timeout=30)
        if resp.status_code != 200:
            print(f"[gauges] stats batch {i} returned {resp.status_code}")
            continue

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

    print(f"[gauges] fetched medians for {len(medians)} sites")
    return medians


def fetch_gauges() -> list[dict]:
    """Fetch latest gauge readings + median comparison for all sites."""
    site_ids = ",".join(s["id"] for s in GAUGE_SITES)
    resp = requests.get(IV_URL, params={
        "format": "json",
        "sites": site_ids,
        "parameterCd": PARAM_CODES,
        "siteStatus": "active",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Fetch daily medians for percent-of-normal
    medians = fetch_daily_medians()

    site_meta = {s["id"]: s for s in GAUGE_SITES}
    results = {}

    for ts in data["value"]["timeSeries"]:
        site_code = ts["sourceInfo"]["siteCode"][0]["value"]
        param_code = ts["variable"]["variableCode"][0]["value"]
        param_name = ts["variable"]["variableName"]
        unit = ts["variable"]["unit"]["unitCode"]
        values = ts["values"][0]["value"]
        latest = values[-1] if values else {}

        if site_code not in results:
            meta = site_meta.get(site_code, {})
            results[site_code] = {
                "site_id": site_code,
                "name": meta.get("name", ts["sourceInfo"]["siteName"]),
                "state": meta.get("state", ""),
                "latitude": ts["sourceInfo"]["geoLocation"]["geogLocation"]["latitude"],
                "longitude": ts["sourceInfo"]["geoLocation"]["geogLocation"]["longitude"],
                "parameters": {},
                "median_discharge_cfs": medians.get(site_code),
                "pct_of_median": None,
            }

        if latest.get("value") and latest["value"] != "-999999":
            results[site_code]["parameters"][param_code] = {
                "name": param_name,
                "value": float(latest["value"]),
                "unit": unit,
                "datetime": latest.get("dateTime"),
            }

    # Compute percent-of-median for discharge
    for site_code, rec in results.items():
        q = rec["parameters"].get("00060", {}).get("value")
        med = rec["median_discharge_cfs"]
        if q and med and med > 0:
            rec["pct_of_median"] = round(q / med * 100, 1)

    gauges = list(results.values())
    print(f"[gauges] fetched {len(gauges)} sites")
    return gauges


if __name__ == "__main__":
    import json
    gauges = fetch_gauges()
    for g in gauges:
        q = g["parameters"].get("00060", {}).get("value")
        print(f"  {g['name']:45s} {q or '—':>8} cfs  "
              f"median: {g['median_discharge_cfs'] or '—':>8}  "
              f"pct: {g['pct_of_median'] or '—'}")
