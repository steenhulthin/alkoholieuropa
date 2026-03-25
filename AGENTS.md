# AGENTS.md

## Repository Purpose

This repository contains:

- a Eurostat XML-to-Parquet preprocessing script under `data/`
- a Python Shiny dashboard under `alcoholandsex/`

The dashboard compares alcohol-consumption habits with sex-satisfaction indicators across European countries.

## Important Files

- `alcoholandsex/app.py`: Shiny UI, reactive filtering, and Plotly chart rendering
- `alcoholandsex/shared.py`: Eurostat loading helpers, labeling, reference-slice filtering, and latest-snapshot logic
- `data/transform_eurostat_xml_to_parquet.py`: SDMX XML extraction and Parquet export
- `run_app.ps1`: app entry point using `alcoholandsex/.venv`
- `run_data.ps1`: data pipeline entry point using `data/.venv`

## Working Agreements For Agents

- Preserve the split between the app environment and the data environment unless explicitly asked to unify them.
- Do not remove project-specific dataset filters without checking whether the dashboard behavior should change.
- Treat `data/processed/*.parquet` as generated artifacts from XML inputs and the transform script.
- Prefer adding pure helper functions over expanding `app.py` further.
- Keep documentation in sync when changing dataset assumptions, run steps, or output file names.
- Avoid destructive git commands. The working tree may already contain user edits.

## Safe Default Workflow

1. Inspect `app.py`, `shared.py`, and `transform_eurostat_xml_to_parquet.py`.
2. Check whether a requested change belongs in:
   - dashboard presentation
   - data loading and normalization
   - XML preprocessing
   - repository documentation
3. If changing business rules, update the relevant file in `specs/`.
4. If changing developer workflow, update `README.md` and `VENV_USAGE.md` if needed.

## Known Architecture Constraints

- The app currently fetches live Eurostat data at startup.
- Label lookups depend on local Parquet files generated from XML reference data.
- Dataset-specific choices such as excluded age bands, removed aggregate geographies, and allowed frequency values are hard-coded.
- There is currently no automated test suite.

## Good Refactor Targets

- Move chart-building into dedicated functions or modules.
- Move dataset metadata and filter rules into config objects.
- Add tests around:
  - `_parse_obs_value`
  - `load_eurostat_*`
  - `filter_reference_slice`
  - `latest_snapshot`
  - XML transformation helpers
