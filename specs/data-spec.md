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
- `*__observations.parquet`

These files are generated from XML inputs in `data/` by [transform_eurostat_xml_to_parquet.py](/mnt/e/prj/dagens_dashboard/alkohol-i-europa/data/transform_eurostat_xml_to_parquet.py).

## Runtime Loading Rules

- the app reads local `*__observations.parquet` files from `data/processed/`
- the dashboard does not call the Eurostat API at runtime
- labels are attached from local Parquet lookup files
- rows are filtered to a project-specific comparison slice
- latest yearly rows are selected per grouping

## Preprocessing Rules

- the data pipeline reads XML metadata from `data/`
- if the XML files do not contain observation rows, the data pipeline fetches the dataset values during preprocessing
- the data pipeline writes local `*__observations.parquet` files used by the dashboard runtime

## Current Project-Specific Filtering Rules

### Shared Filters

- remove EU aggregate geographies such as `EU27_2020`, `EU28`, `EU27_2007`
- remove euro area aggregate codes matching `EA*`
- remove sex total code `T`

### Alcohol Dataset Rules

- allow only age codes:
  - `Y15-24`
  - `Y25-34`
  - `Y35-44`
  - `Y45-64`
  - `Y65-74`
  - `Y_GE75`
- remove frequency codes `NEVER` and `N12M`
- remove matching labels for "never" and "not in the last 12 months"

### Satisfaction Dataset Rules

- keep the dataset's fixed 16+ age slice and do not expose age as a dashboard filter
- remove level code `EURO`

## Aggregation Rules In The App

- alcohol chart: mean `OBS_VALUE` by country and alcohol frequency after selected filters
- map: mean alcohol `OBS_VALUE` by country
- satisfaction chart: mean `OBS_VALUE` by country after selected filters
- scatterplot:
  - alcohol side = sum of country frequency shares
  - satisfaction side = mean of country satisfaction values

## Known Data Coupling

- the app assumes processed observation and lookup files exist for the dataset IDs it loads
- source dimension names are preserved from Eurostat, including names like `frequenc`
- country mapping to ISO-3 is maintained manually in the app
