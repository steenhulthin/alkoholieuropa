# Refactoring Notes

This document captures the highest-value cleanup and refactoring opportunities based on the current implementation.

## 1. Split `app.py` By Responsibility

Today, [app.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/alcoholandsex/app.py) contains:

- data loading
- filter normalization
- chart preparation
- Plotly figure creation
- Shiny UI layout
- inline JavaScript for resize and click binding

Recommended split:

- `alcoholandsex/data_loader.py`: dataset loading and normalization
- `alcoholandsex/chart_builders.py`: Plotly figure functions
- `alcoholandsex/filters.py`: choice generation and selected-code normalization
- `alcoholandsex/ui_helpers.py`: reusable UI bits and JS snippets

This is the biggest maintainability win in the repo.

## 2. Replace Hard-Coded Dataset Rules With Config

Project-specific logic is currently spread across:

- [shared.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/alcoholandsex/shared.py)
- [transform_eurostat_xml_to_parquet.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/data/transform_eurostat_xml_to_parquet.py)
- [app.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/alcoholandsex/app.py)

Examples:

- preferred values for `freq`, `unit`, `citizen`, `quantile`
- allowed age codes
- removed aggregate geographies
- excluded sex totals
- excluded alcohol frequency buckets
- excluded sex-satisfaction levels

Recommended approach:

- add a `dataset_config.py` module
- define one config object per dataset
- let both the transform script and app read the same config

That would reduce drift between preprocessing and app behavior.

## 3. Improve Naming And Domain Clarity

Some current names are functional but unclear:

- `frequenc` mirrors source data, but needs a wrapper constant or alias in app code
- `sat_raw`, `sat_filtered`, `sat_latest` are short but not very expressive
- `_choices` and `_load_data` do multiple things each

Recommended improvements:

- create source-column constants
- use names like `satisfaction_latest_df`
- rename `_choices` to `build_choice_map`
- rename `_normalize_selected_codes` to `normalize_selected_dimension_values`

## 4. Add Tests Around Pure Functions First

Best first test targets:

- observation parsing in `shared.py`
- latest snapshot grouping behavior
- XML dimension and codelist extraction
- project filter behavior for both datasets

Suggested test files:

- `tests/test_shared.py`
- `tests/test_transform_eurostat_xml_to_parquet.py`

## 5. Reduce Inline Frontend Script Surface

The current inline script in [app.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/alcoholandsex/app.py) works, but it is long enough to deserve extraction.

Recommended cleanup:

- move the script into `alcoholandsex/static/plotly-bindings.js` or a similar location
- give the bindings named functions
- document the click contract with `map_country_click` and `scatter_country_click`

## 6. Tighten Dependency And Repo Hygiene

Recommended cleanup:

- pin versions in `app_requirements.txt` and `data_requirements.txt`
- expand `.gitignore` for `.venv/`, `.pytest_cache/`, `.DS_Store`, generated Parquet if desired
- add a root `README.md` with setup and architecture notes
- add tests before doing larger behavioral refactors

## Suggested Refactor Order

1. Add README, agent file, and specs
2. Add tests for current behavior
3. Extract app helpers into modules without changing behavior
4. Introduce dataset config objects
5. Revisit chart logic and naming cleanup
