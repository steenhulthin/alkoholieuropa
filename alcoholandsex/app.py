import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from shiny import App, reactive, ui
from shinywidgets import output_widget, render_widget

from shared import (
    app_dir,
    attach_labels,
    display_label,
    filter_reference_slice,
    latest_snapshot,
    load_eurostat,
    normalize_display_labels,
)


def _empty_plot(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, showarrow=False, xref="paper", yref="paper")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=700, width=None, autosize=True, margin=dict(l=20, r=20, t=60, b=20))
    return fig


def _frequency_rank(label: str) -> int:
    text = str(label).lower()
    if "every day" in text or "daily" in text:
        return 0
    if "every week" in text or "weekly" in text:
        return 1
    if "every month" in text or "monthly" in text:
        return 2
    if "less" in text and "month" in text:
        return 3
    if "never" in text:
        return 4
    return 99


def _age_code_rank(code: str) -> int:
    order = {
        "Y15-24": 0,
        "Y25-34": 1,
        "Y35-44": 2,
        "Y45-64": 3,
        "Y65-74": 4,
        "Y_GE75": 5,
    }
    return order.get(str(code).upper(), 99)


_ISO3_BY_GEO = {
    "AL": "ALB",
    "AT": "AUT",
    "BA": "BIH",
    "BE": "BEL",
    "BG": "BGR",
    "CH": "CHE",
    "CY": "CYP",
    "CZ": "CZE",
    "DE": "DEU",
    "DK": "DNK",
    "EE": "EST",
    "EL": "GRC",
    "ES": "ESP",
    "FI": "FIN",
    "FR": "FRA",
    "HR": "HRV",
    "HU": "HUN",
    "IE": "IRL",
    "IS": "ISL",
    "IT": "ITA",
    "LI": "LIE",
    "LT": "LTU",
    "LU": "LUX",
    "LV": "LVA",
    "ME": "MNE",
    "MK": "MKD",
    "MT": "MLT",
    "NL": "NLD",
    "NO": "NOR",
    "PL": "POL",
    "PT": "PRT",
    "RO": "ROU",
    "RS": "SRB",
    "SE": "SWE",
    "SI": "SVN",
    "SK": "SVK",
    "TR": "TUR",
    "UK": "GBR",
    "XK": "XKX",
}


def _geo_to_iso3(code: str) -> str | None:
    if not code:
        return None
    return _ISO3_BY_GEO.get(str(code).strip().upper())


def _load_data():
    alcohol_raw = load_eurostat("hlth_ehis_al1c")
    alcohol_labeled = attach_labels(alcohol_raw, "hlth_ehis_al1c")
    alcohol_filtered = filter_reference_slice(
        alcohol_labeled,
        keep_dims=["frequenc", "sex", "age", "geo"],
    )
    alcohol_latest = latest_snapshot(
        alcohol_filtered,
        group_cols=["frequenc", "sex", "age", "geo"],
    )
    alcohol_latest = normalize_display_labels(
        alcohol_latest,
        [
            ("frequenc", "frequenc_label", "frequency"),
            ("sex", "sex_label", "sex"),
            ("age", "age_label", "age"),
        ],
    )

    sat_raw = load_eurostat("sdg_03_20")
    sat_labeled = attach_labels(sat_raw, "sdg_03_20")
    sat_filtered = filter_reference_slice(
        sat_labeled,
        keep_dims=["sex", "geo", "levels"],
    )
    sat_latest = latest_snapshot(
        sat_filtered,
        group_cols=["sex", "geo", "levels"],
    )
    sat_latest = normalize_display_labels(
        sat_latest,
        [("sex", "sex_label", "sex")],
    )

    return alcohol_latest, sat_latest


try:
    alcohol_df, satisfaction_df = _load_data()
    load_error = ""
except Exception as exc:
    alcohol_df = pd.DataFrame()
    satisfaction_df = pd.DataFrame()
    load_error = str(exc)


def _choices(
    df: pd.DataFrame,
    code_col: str,
    label_col: str,
    by_frequency: bool = False,
    by_age: bool = False,
    kind: str | None = None,
):
    if df.empty or code_col not in df.columns:
        return {}
    labels = df[label_col] if label_col in df.columns else df[code_col]
    pairs = (
        pd.DataFrame({"code": df[code_col], "label": labels})
        .dropna(subset=["code"])
        .drop_duplicates()
    )
    pairs["display_label"] = [
        display_label(code, label, kind or "")
        for code, label in zip(pairs["code"], pairs["label"])
    ]
    if by_frequency:
        pairs["rank"] = pairs["display_label"].map(_frequency_rank)
        pairs = pairs.sort_values(["rank", "display_label"])
    elif by_age:
        pairs["rank"] = pairs["code"].map(_age_code_rank)
        pairs = pairs.sort_values(["rank", "display_label"])
    else:
        pairs = pairs.sort_values("display_label")
    return {row.code: row.display_label for row in pairs.itertuples(index=False)}


def _normalize_selected_codes(
    selected: list[str] | tuple[str, ...] | str | None,
    df: pd.DataFrame,
    code_col: str,
    label_col: str,
) -> list[str]:
    if not selected or df.empty or code_col not in df.columns:
        return []
    if isinstance(selected, str):
        selected = [selected]
    labels = df[label_col] if label_col in df.columns else df[code_col]
    pairs = (
        pd.DataFrame({"code": df[code_col].astype(str), "label": labels.astype(str)})
        .dropna(subset=["code"])
        .drop_duplicates()
    )
    code_lookup: dict[str, str] = {}
    for row in pairs.itertuples(index=False):
        code = str(row.code)
        label = str(row.label)
        code_lookup[code] = code
        code_lookup[label] = code
        code_lookup[f"{label} ({code})"] = code

    out: list[str] = []
    for item in selected:
        item_str = str(item)
        if item_str in code_lookup:
            out.append(code_lookup[item_str])
            continue
        if item_str.endswith(")") and "(" in item_str:
            parsed_code = item_str.rsplit("(", 1)[1].rstrip(")").strip()
            if parsed_code in code_lookup:
                out.append(code_lookup[parsed_code])
    return sorted(set(out))


sex_choices = _choices(alcohol_df, "sex", "sex_label", kind="sex")
age_choices = _choices(alcohol_df, "age", "age_label", by_age=True, kind="age")
frequency_choices = _choices(
    alcohol_df,
    "frequenc",
    "frequenc_label",
    by_frequency=True,
    kind="frequency",
)
sex_default = list(sex_choices.keys())
age_default = list(age_choices.keys())
frequency_default = [
    code for code, label in frequency_choices.items() if label in {"Daily", "Weekly"}
]

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_checkbox_group("sex", "Sex", choices=sex_choices, selected=sex_default),
        ui.input_checkbox_group("age", "Age group", choices=age_choices, selected=age_default),
        ui.input_checkbox_group(
            "frequency_types",
            "Frequency type",
            choices=frequency_choices,
            selected=frequency_default,
        ),
        title="Filter controls",
    ),
    ui.card(
        ui.card_header("Country map (click a country to filter all charts)"),
        ui.card_body(
            output_widget("country_map", width="100%", height="100%"),
            class_="p-0",
        ),
    ),
    ui.navset_tab(
        ui.nav_panel(
            "Alcohol Habits",
            ui.card(
                ui.card_header("Alcohol habits by country"),
                ui.card_body(
                    output_widget("alcohol_chart", width="100%", height="100%"),
                    class_="p-0",
                ),
            ),
        ),
        ui.nav_panel(
            "Sex Satisfaction",
            ui.card(
                ui.card_header("Sex satisfaction level by country"),
                ui.p("Not divided into age groups in this dataset (population aged 16+)."),
                ui.p("Frequency type does not affect this chart."),
                ui.card_body(
                    output_widget("satisfaction_chart", width="100%", height="100%"),
                    class_="p-0",
                ),
            ),
        ),
        ui.nav_panel(
            "Relationship",
            ui.card(
                ui.card_header("Alcohol consumption vs sex satisfaction (scatterplot)"),
                ui.card_body(
                    output_widget("scatter_chart", width="100%", height="100%"),
                    class_="p-0",
                ),
            ),
        ),
    ),
    ui.tags.script(
        """
        (() => {
          const observed = new WeakSet();
          const ro = new ResizeObserver((entries) => {
            for (const entry of entries) {
              const plotEl = entry.target.querySelector('.js-plotly-plot') || entry.target;
              if (window.Plotly && plotEl) {
                window.requestAnimationFrame(() => {
                  try { window.Plotly.Plots.resize(plotEl); } catch (_) {}
                });
              }
            }
          });

          const watchPlots = () => {
            document.querySelectorAll('#country_map, #alcohol_chart, #satisfaction_chart, #scatter_chart, .js-plotly-plot')
              .forEach((el) => {
                if (!observed.has(el)) {
                  observed.add(el);
                  ro.observe(el);
                }
                if (window.Plotly && el.classList.contains('js-plotly-plot')) {
                  try { window.Plotly.Plots.resize(el); } catch (_) {}
                }
              });
          };

          const extractCountry = (pt) => {
            if (!pt) return null;
            const cd = pt.customdata;
            if (Array.isArray(cd) && cd.length) return cd[0];
            if (typeof cd === 'string') return cd;
            return null;
          };

          const bindClick = (containerId, inputId) => {
            const root = document.getElementById(containerId);
            const plot = root ? root.querySelector('.js-plotly-plot') : null;
            if (!plot) return;
            const marker = `bound_${inputId}`;
            if (plot.dataset[marker]) return;
            plot.dataset[marker] = "1";

            plot.on('plotly_click', (evt) => {
              plot.dataset.lastPointClick = String(Date.now());
              const country = extractCountry(evt?.points?.[0]);
              if (!country) return;
              Shiny.setInputValue(inputId, { country, nonce: Date.now() }, { priority: 'event' });
            });

            root.addEventListener('click', (evt) => {
              const recentPointClick = Number(plot.dataset.lastPointClick || "0");
              if (Date.now() - recentPointClick < 250) return;
              if (evt.target.closest('.modebar')) return;
              Shiny.setInputValue(`${inputId}_clear`, { nonce: Date.now() }, { priority: 'event' });
            });
          };

          watchPlots();
          bindClick('country_map', 'map_country_click');
          bindClick('scatter_chart', 'scatter_country_click');
          new MutationObserver(watchPlots).observe(document.body, { childList: true, subtree: true });
          new MutationObserver(() => {
            bindClick('country_map', 'map_country_click');
            bindClick('scatter_chart', 'scatter_country_click');
          }).observe(document.body, { childList: true, subtree: true });
          window.addEventListener('load', watchPlots, { once: true });
          window.addEventListener('resize', watchPlots);
        })();
        """
    ),
    ui.include_css(app_dir / "styles.css"),
    title="Alcohol and Sex Dashboard",
    fillable=False,
)


def server(input, output, session):
    selected_country = reactive.value(None)

    @reactive.effect
    @reactive.event(input.map_country_click)
    def _map_country_click():
        payload = input.map_country_click()
        if not payload:
            return
        country = payload.get("country") if isinstance(payload, dict) else None
        if not country:
            return
        current = selected_country.get()
        selected_country.set(None if current == country else country)

    @reactive.effect
    @reactive.event(input.map_country_click_clear)
    def _map_country_click_clear():
        payload = input.map_country_click_clear()
        if not payload:
            return
        selected_country.set(None)

    @reactive.effect
    @reactive.event(input.scatter_country_click)
    def _scatter_country_click():
        payload = input.scatter_country_click()
        if not payload:
            return
        country = payload.get("country") if isinstance(payload, dict) else None
        if not country:
            return
        selected_country.set(country)

    @reactive.calc
    def alcohol_base():
        if alcohol_df.empty:
            return alcohol_df
        data = alcohol_df.copy()
        selected_sex = _normalize_selected_codes(input.sex(), alcohol_df, "sex", "sex_label")
        selected_age = _normalize_selected_codes(input.age(), alcohol_df, "age", "age_label")
        selected_freq = _normalize_selected_codes(
            input.frequency_types(), alcohol_df, "frequenc", "frequenc_label"
        )
        if selected_sex:
            data = data.loc[data["sex"].isin(selected_sex)]
        if selected_age:
            data = data.loc[data["age"].isin(selected_age)]
        if not selected_freq:
            return data.iloc[0:0].copy()
        data = data.loc[data["frequenc"].isin(selected_freq)]
        if data.empty:
            return data
        group_cols = ["geo", "frequenc"]
        if "geo_label" in data.columns:
            group_cols.append("geo_label")
        if "frequenc_label" in data.columns:
            group_cols.append("frequenc_label")
        return data.groupby(group_cols, as_index=False)["OBS_VALUE"].mean()

    @reactive.calc
    def alcohol_selected():
        data = alcohol_base()
        if data.empty:
            return data
        country = selected_country.get()
        if country:
            data = data.loc[data["geo"] == country]
        return data

    @reactive.calc
    def satisfaction_country():
        if satisfaction_df.empty:
            return satisfaction_df
        selected_sex = _normalize_selected_codes(input.sex(), satisfaction_df, "sex", "sex_label")
        data = satisfaction_df.copy()
        if selected_sex:
            data = data.loc[data["sex"].isin(selected_sex)]
        country = selected_country.get()
        if country:
            data = data.loc[data["geo"] == country]
        if data.empty:
            return data
        country_cols = ["geo"]
        if "geo_label" in data.columns:
            country_cols.append("geo_label")
        grouped = data.groupby(country_cols, as_index=False)["OBS_VALUE"].mean()
        return grouped.sort_values("OBS_VALUE", ascending=False)

    @render_widget
    def country_map():
        if load_error:
            return _empty_plot(f"Data loading failed: {load_error}")

        if not _normalize_selected_codes(input.frequency_types(), alcohol_df, "frequenc", "frequenc_label"):
            return _empty_plot("Select one or more frequency types to show the country map.")

        data = alcohol_base()
        if data.empty:
            return _empty_plot("No data available for the selected filters.")

        country_cols = ["geo"]
        if "geo_label" in data.columns:
            country_cols.append("geo_label")
        map_df = data.groupby(country_cols, as_index=False)["OBS_VALUE"].mean()
        map_df["iso3"] = map_df["geo"].map(_geo_to_iso3)
        map_df = map_df.dropna(subset=["iso3"])
        if map_df.empty:
            return _empty_plot("No mappable country codes for current filters.")

        hover_col = "geo_label" if "geo_label" in map_df.columns else "geo"
        fig = px.choropleth(
            map_df,
            locations="iso3",
            color="OBS_VALUE",
            hover_name=hover_col,
            custom_data=["geo"],
            color_continuous_scale="Blues",
            labels={"OBS_VALUE": "Alcohol habits share (%)"},
        )
        fig.update_geos(
            scope="europe",
            showcountries=True,
            countrycolor="white",
            showcoastlines=True,
            coastlinecolor="white",
            fitbounds="locations",
        )
        fig.update_layout(
            height=520,
            margin=dict(l=10, r=10, t=30, b=10),
            coloraxis_colorbar=dict(title="Share (%)"),
        )

        current_country = selected_country.get()
        if current_country:
            selected_row = map_df.loc[map_df["geo"] == current_country]
            if not selected_row.empty:
                fig.add_trace(
                    go.Choropleth(
                        locations=selected_row["iso3"],
                        z=[1] * len(selected_row),
                        customdata=selected_row[["geo"]].to_numpy(),
                        locationmode="ISO-3",
                        showscale=False,
                        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                        marker_line_color="#111111",
                        marker_line_width=3,
                        hoverinfo="skip",
                    )
                )
        return fig

    @render_widget
    def alcohol_chart():
        if load_error:
            return _empty_plot(f"Data loading failed: {load_error}")
        data = alcohol_selected()
        if data.empty:
            return _empty_plot("Select one or more frequency types to show alcohol data.")

        country_col = "geo_label" if "geo_label" in data.columns else "geo"
        freq_col = "frequenc_label" if "frequenc_label" in data.columns else "frequenc"
        plot_df = data[[country_col, freq_col, "OBS_VALUE"]].copy()
        pivot = plot_df.pivot_table(index=country_col, columns=freq_col, values="OBS_VALUE", aggfunc="mean").fillna(0)
        freq_order = sorted(list(pivot.columns), key=_frequency_rank)
        pivot = pivot[freq_order]

        sort_base = freq_order[0] if freq_order else None
        if sort_base is not None:
            pivot = pivot.assign(_sort_high=pivot[sort_base], _sort_total=pivot.sum(axis=1))
            pivot = pivot.sort_values(["_sort_high", "_sort_total"], ascending=False).drop(
                columns=["_sort_high", "_sort_total"]
            )

        plot_long = (
            pivot.reset_index()
            .melt(id_vars=[country_col], value_vars=freq_order, var_name="frequency", value_name="share")
        )
        fig = px.bar(
            plot_long,
            x=country_col,
            y="share",
            color="frequency",
            category_orders={"frequency": freq_order, country_col: list(pivot.index)},
            labels={country_col: "Country", "share": "Share (%)", "frequency": "Frequency type"},
            title="Alcohol habits by country",
        )
        fig.update_layout(
            barmode="stack",
            xaxis_tickangle=-55,
            legend_title_text="Frequency type",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            width=None,
            autosize=True,
            height=780,
            margin=dict(l=50, r=20, t=90, b=140),
        )
        return fig

    @render_widget
    def satisfaction_chart():
        if load_error:
            return _empty_plot(f"Data loading failed: {load_error}")
        data = satisfaction_country()
        if data.empty:
            return _empty_plot("No sex satisfaction data for the selected sex.")
        country_col = "geo_label" if "geo_label" in data.columns else "geo"
        plot_df = data.sort_values("OBS_VALUE", ascending=False)
        fig = px.bar(
            plot_df,
            x=country_col,
            y="OBS_VALUE",
            labels={country_col: "Country", "OBS_VALUE": "Share (%)"},
            title="Sex satisfaction level by country (no age-group split)",
        )
        fig.update_traces(marker_color="#3D7EA6")
        fig.update_layout(
            xaxis_tickangle=-55,
            showlegend=False,
            width=None,
            autosize=True,
            height=780,
            margin=dict(l=50, r=20, t=80, b=140),
        )
        return fig

    @render_widget
    def scatter_chart():
        if load_error:
            return _empty_plot(f"Data loading failed: {load_error}")
        if not _normalize_selected_codes(input.frequency_types(), alcohol_df, "frequenc", "frequenc_label"):
            return _empty_plot("Select one or more frequency types to show the relationship chart.")
        alcohol = alcohol_selected()
        sat = satisfaction_country()
        if alcohol.empty or sat.empty:
            return _empty_plot("Not enough overlapping country data for this scatterplot.")
        geo_col = "geo"
        alcohol_total = alcohol.groupby(geo_col, as_index=False)["OBS_VALUE"].sum().rename(
            columns={"OBS_VALUE": "alcohol_value"}
        )
        sat_country = sat.groupby(geo_col, as_index=False)["OBS_VALUE"].mean().rename(
            columns={"OBS_VALUE": "satisfaction_value"}
        )
        merged = alcohol_total.merge(sat_country, on=geo_col, how="inner")
        if merged.empty:
            return _empty_plot("No country overlap between alcohol and satisfaction datasets.")
        if "geo_label" in alcohol.columns:
            geo_labels = alcohol[[geo_col, "geo_label"]].drop_duplicates()
            merged = merged.merge(geo_labels, on=geo_col, how="left")
            hover_col = "geo_label"
        else:
            hover_col = geo_col

        fig = px.scatter(
            merged,
            x="satisfaction_value",
            y="alcohol_value",
            hover_name=hover_col,
            custom_data=["geo"],
            labels={
                "satisfaction_value": "Sex satisfaction share (%)",
                "alcohol_value": "Alcohol consumption share (%)",
            },
            title="Alcohol consumption vs sex satisfaction by country",
        )
        fig.update_traces(marker=dict(color="#2D6A4F", size=9))
        fig.update_layout(
            width=None,
            autosize=True,
            height=780,
            showlegend=False,
            margin=dict(l=60, r=20, t=80, b=60),
        )
        return fig


app = App(app_ui, server)
