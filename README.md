# Colorado River Basin — Watershed Data Aggregator

A live data aggregator for the Colorado River Basin, built for the owockibot.xyz bioregional bounty.

**Bounty #237** — "Build a watershed data aggregator for Colorado River Basin"  
**Reward:** $35 USDC  
**Claimer:** Nou (Techne / RegenHub, LCA) · 0xC37604A1dD79Ed50A5c2943358db85CB743dd3e2  
**Live demo:** https://nou-techne.github.io/watershed-data-collection/

---

## What It Does

Pulls three streams of public watershed data for the Colorado River Basin and serves a live dashboard:

| Data Layer | Source | Update Frequency |
|---|---|---|
| Stream gauges (discharge + gage height) | USGS Water Services API | Twice daily (source updates every 15 min) |
| Reservoir levels (Lake Powell) | USGS Water Services API | Twice daily (source updates every 15 min) |
| Snowpack — Snow Water Equivalent | NRCS SNOTEL / AWDB REST API | Twice daily (source updates daily) |

A GitHub Actions workflow runs twice daily, fetches fresh data from all three sources, writes it to `docs/data.json`, and GitHub Pages serves the live dashboard.

---

## Data Sources

### USGS Water Services API
Free, no authentication required.  
Docs: https://waterservices.usgs.gov/

Key sites monitored:

| Site ID | Name | Parameters |
|---|---|---|
| 09380000 | Colorado River at Lees Ferry, AZ | Discharge (cfs), Gage height (ft) |
| 09402500 | Colorado River near Grand Canyon, AZ | Discharge, Gage height |
| 09421500 | Colorado River below Hoover Dam, AZ-NV | Gage height |
| 09379900 | Glen Canyon Dam (Lake Powell) | Reservoir elevation (ft) |
| 09163500 | Colorado River near Colorado-Utah state line | Discharge |
| 09070500 | Colorado River near Dotsero, CO | Discharge |
| 09095500 | Colorado River near Cameo, CO | Discharge |
| 09105000 | Colorado River near Cameo (Glenwood) | Discharge |

### NRCS SNOTEL — AWDB REST API
Free, no authentication required.  
Docs: https://wcc.sc.egov.usda.gov/awdbRestApi/swagger-ui/index.html

Pulls Snow Water Equivalent (SWE) and precipitation from SNOTEL stations in HUC basins 14 (Upper Colorado) and 15 (Lower Colorado). Currently ~100+ active stations across Colorado, Utah, Wyoming, and New Mexico headwaters.

### Bureau of Reclamation (via USGS)
Lake Powell and Lake Mead reservoir elevation data accessed via USGS gauge sites co-located with the dams. No authentication required.

---

## Project Structure

```
watershed-data-collection/
├── src/
│   ├── fetch_gauges.py        # USGS stream gauge fetcher
│   ├── fetch_snowpack.py      # NRCS SNOTEL fetcher
│   ├── fetch_reservoirs.py    # USGS reservoir elevation fetcher
│   └── aggregate.py           # Combines all sources → docs/data.json
├── docs/
│   ├── index.html             # Live dashboard (GitHub Pages)
│   └── data.json              # Latest aggregated data snapshot
├── .github/
│   └── workflows/
│       └── update-data.yml    # Twice-daily refresh via GitHub Actions
└── requirements.txt
```

---

## Running Locally

```bash
pip install -r requirements.txt
python src/aggregate.py
# Writes fresh data to docs/data.json
# Open docs/index.html in a browser
```

---

## Relation to Bioregional Infrastructure

This tool is a unit of the knowledge commons described in the owockibot bioregional thesis. Every fetch enriches a shared, verifiable, queryable dataset for the Colorado River Basin. The JSON output is structured to be:

- Machine-readable (for AI agents)
- Human-readable (for the dashboard)
- Composable (for future aggregation into basin-wide indicators)

This is the data layer that a Bioregional Financing Facility would need to track outcomes: reservoir levels, watershed health, snowpack as a forward indicator of spring runoff.

---

Built by [Nou](https://github.com/nou-techne) · [Techne / RegenHub, LCA](https://regenhub.xyz) · Boulder, Colorado
