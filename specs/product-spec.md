# Product Specification

## Product Name

Alcohol in Europe Dashboard

## Purpose

Provide an exploratory dashboard that lets users compare alcohol-consumption habits and sex-satisfaction indicators across European countries using Eurostat data.

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

Default selection: 
`Sex` should be: all
`Age group` shoudl be: all
`frequency type` should be: "Daily" and "weekly"

All available values are populated from the alcohol dataset after labels are attached.

### Country Map

- displays average alcohol indicator values by country - The share and colors should only be shown when one or more frequency type(s) is selected
- clicking a country toggles it as the selected cross-chart filter - Clicking another country shoud select that. Clicking the map on no country should clear the selection. 
- when a country is selected, it is outlined on the map

### Alcohol Habits Tab

- stacked bar chart
- grouped by country
- stacked by alcohol frequency label
- filtered by selected sex, age group, frequency values, and selected country

### Sex Satisfaction Tab

- bar chart by country
- filtered by selected sex and selected country
- not split by age group in the current dataset usage
- Frequence type not used for this graph (make user aware)

### Relationship Tab

- Only show numbers if one or more `Frequency type` is selected.
- scatterplot comparing country-level alcohol and satisfaction aggregates
- clicking a point sets the selected country

## Current Functional Rules

- the app loads both datasets at startup
- if loading fails, the UI shows an empty Plotly figure with the error message
- all charts render a fallback empty figure when the filtered result is empty
- the dashboard uses the latest yearly snapshot available per grouping

## Non-Goals In The Current Build

- no editing or data submission
- no persisted user state
- no offline cached API mode
- no automated explanation layer or narrative text generation
