# Technical Specification

## Stack

- Python
- Shiny for Python
- Plotly
- pandas
- pyarrow for Parquet export
- PowerShell helper scripts for local execution

## Runtime Architecture

### Data Preprocessing

- entry point: [run_data.ps1](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/run_data.ps1)
- script: [transform_eurostat_xml_to_parquet.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/data/transform_eurostat_xml_to_parquet.py)
- input: XML files in `data/`
- output: Parquet files in `data/processed/`, including local observation extracts used by the app

### Application Runtime

- entry point: [run_app.ps1](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/run_app.ps1)
- app module: [app.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/alcoholandsex/app.py)
- shared helpers: [shared.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/alcoholandsex/shared.py)

## Current Module Responsibilities

### `alcoholandsex/app.py`

- load both datasets at import time
- define filter choices and defaults
- define Shiny UI
- render a sidebar dashboard description and source references
- prepare filtered DataFrames
- render Plotly figures
- inject inline JavaScript for Plotly resizing

### `alcoholandsex/shared.py`

- load local observation Parquet files from `data/processed/`
- parse observation values
- attach labels from processed Parquet tables
- reduce datasets to a preferred reference slice
- select latest yearly snapshot per grouping

### `data/transform_eurostat_xml_to_parquet.py`

- parse SDMX XML
- extract codelists
- extract dimensions
- extract observations when present in XML
- fetch observations during preprocessing when XML is structure-only
- attach labels to observations
- apply project-specific filters
- write Parquet outputs

## Technical Debt To Track

- startup data loading happens at module import time
- app code mixes UI, data prep, and visualization logic
- project-specific rules are duplicated across app/runtime and preprocessing
- no tests or linting configuration are present
- dependency versions are not pinned

## Recommended Near-Term Deliverables

1. Add automated tests for pure helpers and transform behavior.
2. Extract chart builders and filter helpers out of `app.py`.
3. Create a shared dataset configuration module used by both app and preprocessing.
4. Move inline JavaScript into a dedicated static asset.
