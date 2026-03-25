# Product Specification

## Product Name

Alcohol in Europe Dashboard

## Purpose

Provide an exploratory dashboard that lets users compare alcohol-consumption habits and sex-satisfaction indicators across European countries using locally prepared Eurostat data files.

## Current User Goals

- compare countries visually on a Europe map
- see alcohol-consumption habit distribution by country
- see sex-satisfaction share by country
- inspect the relationship between both indicators in a scatterplot
- filter the analysis by sex, age group, and alcohol-consumption frequency type

## Current Screens And Behaviors

### Sidebar Filters

- `Sex`: multi-select checkbox group - represented with "Female" and "Male"
- `Age group`: multi-select checkbox group - represented with "15-24", "25-34", "35-44", "45-64", "65-74" and "Over 74"
- `Frequency type`: multi-select checkbox group - represented with "Daily", "Weekly", "Monthly", "Less than monthly" and "Never or less than yearly"
- Under the filters, show a short dashboard description explaining that the user can compare countries on the map, inspect the bar charts, and review the scatterplot relationship
- Under that description, show source references linking to the Eurostat alcohol dataset and the Eurostat perceived-health dataset
- The dashboard does not support country click interactions between the map and charts or between charts

Default selection: 
`Sex` should be: all
`Age group` should be: all
`frequency type` should be: "Daily" and "Weekly"

All available values are populated from the alcohol dataset after labels are attached.

### Country Map

- displays average alcohol indicator values by country - The share and colors should only be shown when one or more frequency type(s) is selected
- no country-click selection or cross-chart filtering is applied from the map

### Alcohol Habits Tab

- stacked bar chart
- grouped by country
- stacked by alcohol frequency label
- filtered by selected sex, age group, and frequency values

### Sex Satisfaction Tab

- bar chart by country
- filtered by selected sex
- not split by age group in the current dataset usage
- Frequency type not used for this graph (make user aware)

### Relationship Tab

- Only show numbers if one or more `Frequency type` is selected.
- scatterplot comparing country-level alcohol and satisfaction aggregates
- no click selection is applied from scatterplot points

## Current Functional Rules

- the app loads both datasets at startup
- the app reads dashboard data from local files in `data/` at runtime and does not depend on live API calls
- if loading fails, the UI shows an empty Plotly figure with the error message
- all charts render a fallback empty figure when the filtered result is empty
- the dashboard uses the latest yearly snapshot available per grouping

## Non-Goals In The Current Build

- no editing or data submission
- no persisted user state
- no offline cached API mode
- no automated explanation layer or narrative text generation
