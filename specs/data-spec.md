# Data Specification

## Data Sources

### 1. `hlth_ehis_al1c`

Used for alcohol-consumption habits.

Expected working dimensions in the app:

- `geo`
- `sex`
- `age`
- `frequenc`
- `year`
- `OBS_VALUE`

### 2. `sdg_03_20`

Used for sex-satisfaction indicators.

Expected working dimensions in the app:

- `geo`
- `sex`
- `levels`
- `year`
- `OBS_VALUE`

## Local Reference Data

The project stores extracted SDMX metadata in `data/processed/`:

- `*__dimensions.parquet`
- `*__codelists.parquet`
- optionally `*__observations.parquet`

These files are generated from XML inputs in `data/` by [transform_eurostat_xml_to_parquet.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/data/transform_eurostat_xml_to_parquet.py).

## Runtime Loading Rules

- the app prefers Eurostat JSON loading
- the app falls back to TSV loading if JSON fails
- labels are attached from local Parquet lookup files
- rows are filtered to a project-specific comparison slice
- latest yearly rows are selected per grouping

## Current Project-Specific Filtering Rules

### Shared Filters

- remove EU aggregate geographies such as `EU27_2020`, `EU28`, `EU27_2007`
- remove euro area aggregate codes matching `EA*`
- remove sex total code `T`
- allow only age codes:
  - `Y15-24`
  - `Y25-34`
  - `Y35-44`
  - `Y45-64`
  - `Y65-74`
  - `Y_GE75`

### Alcohol Dataset Rules

- remove frequency codes `NEVER` and `N12M`
- remove matching labels for "never" and "not in the last 12 months"

### Satisfaction Dataset Rules

- remove level code `EURO`

## Aggregation Rules In The App

- alcohol chart: mean `OBS_VALUE` by country and alcohol frequency after selected filters
- map: mean alcohol `OBS_VALUE` by country
- satisfaction chart: mean `OBS_VALUE` by country after selected filters
- scatterplot:
  - alcohol side = sum of country frequency shares
  - satisfaction side = mean of country satisfaction values

## Known Data Coupling

- the app assumes processed lookup files exist for the dataset IDs it loads
- source dimension names are preserved from Eurostat, including names like `frequenc`
- country mapping to ISO-3 is maintained manually in the app
