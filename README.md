# Alcohol in Europe Dashboard

This repository contains a small two-part data app:

- a preprocessing script that extracts Eurostat SDMX XML structure data into Parquet lookup tables
- a Python Shiny dashboard that combines those local lookup tables with live Eurostat API data

The current dashboard explores alcohol consumption habits and sex satisfaction across European countries.

## Project Structure

```text
.
├── alcoholandsex/
│   ├── app.py
│   ├── shared.py
│   ├── styles.css
│   └── app_requirements.txt
├── data/
│   ├── transform_eurostat_xml_to_parquet.py
│   ├── processed/
│   ├── *.xml
│   ├── *_doc.md
│   └── data_requirements.txt
├── docs/
│   └── refactoring-notes.md
├── specs/
│   ├── product-spec.md
│   ├── data-spec.md
│   └── technical-spec.md
├── AGENTS.md
├── VENV_USAGE.md
├── run_app.ps1
└── run_data.ps1
```

## What The App Does

The dashboard currently:

- loads alcohol-consumption survey data from Eurostat dataset `hlth_ehis_al1c`
- loads sex-satisfaction data from Eurostat dataset `sdg_03_20`
- enriches both datasets with local labels from Parquet codelist exports
- filters to a project-specific comparison slice
- shows:
  - a Europe choropleth map
  - a stacked alcohol-habits bar chart
  - a sex-satisfaction bar chart
  - a country-level scatterplot comparing both indicators

Country selection is interactive: clicking the map filters the other charts.

## Setup

This project uses separate virtual environments for the data pipeline and the app.

Install data dependencies:

```powershell
.\data\.venv\Scripts\python.exe -m pip install -r .\data\data_requirements.txt
```

Install app dependencies:

```powershell
.\alcoholandsex\.venv\Scripts\python.exe -m pip install -r .\alcoholandsex\app_requirements.txt
```

See [VENV_USAGE.md](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/VENV_USAGE.md) for the existing workflow.

## Run The Data Pipeline

The preprocessing script reads Eurostat XML files from `data/` and writes Parquet tables to `data/processed/`.

```powershell
.\run_data.ps1
```

This script currently produces:

- `__codelists.parquet`
- `__dimensions.parquet`
- optionally `__observations.parquet` when the XML contains observation rows

## Run The App

```powershell
.\run_app.ps1
```

By default the app runs on port `8000`.

## Data Flow

1. XML metadata is transformed into local Parquet lookup tables by [transform_eurostat_xml_to_parquet.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/data/transform_eurostat_xml_to_parquet.py).
2. The app fetches live Eurostat data in JSON format and falls back to TSV when needed in [shared.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/alcoholandsex/shared.py).
3. Local codelists and dimensions are used to attach human-readable labels.
4. The app applies a project-specific filtered comparison slice and takes the latest yearly snapshot per grouping.
5. Plotly charts render the filtered result inside a Shiny app in [app.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/alcoholandsex/app.py).

## Current Limitations

- The dashboard depends on live Eurostat API availability at runtime.
- The app and data pipeline are coupled through dataset-specific assumptions and file naming.
- Project-specific filtering rules are embedded directly in code rather than described as configuration.
- There are no automated tests yet.

## Documentation Added In This Repo

- [AGENTS.md](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/AGENTS.md)
- [docs/refactoring-notes.md](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/docs/refactoring-notes.md)
- [specs/product-spec.md](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/specs/product-spec.md)
- [specs/data-spec.md](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/specs/data-spec.md)
- [specs/technical-spec.md](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/specs/technical-spec.md)

## Next Recommended Steps

1. Split dataset loading, filtering, and chart-building out of `app.py`.
2. Move dataset-specific filter rules into declarative configuration.
3. Add smoke tests for the transform script and pure-data helper functions.
4. Pin dependency versions and expand `.gitignore` for local environments and generated files.
