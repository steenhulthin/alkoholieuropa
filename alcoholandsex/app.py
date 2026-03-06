import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from shiny import App, reactive, ui
from shinywidgets import output_widget, render_widget

from shared import (
    app_dir,
    attach_labels,
    filter_reference_slice,
    latest_snapshot,
    load_eurostat,
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

    return alcohol_latest, sat_latest


try:
    alcohol_df, satisfaction_df = _load_data()
    load_error = ""
except Exception as exc:
    alcohol_df = pd.DataFrame()
    satisfaction_df = pd.DataFrame()
    load_error = str(exc)


def _choices(df: pd.DataFrame, code_col: str, label_col: str, by_frequency: bool = False):
    if df.empty or code_col not in df.columns:
        return {}
    labels = df[label_col] if label_col in df.columns else df[code_col]
    pairs = (
        pd.DataFrame({"code": df[code_col], "label": labels})
        .dropna(subset=["code"])
        .drop_duplicates()
    )
    if by_frequency:
        pairs["rank"] = pairs["label"].map(_frequency_rank)
        pairs = pairs.sort_values(["rank", "label"])
    else:
        pairs = pairs.sort_values("label")
    return {f"{row.label} ({row.code})": row.code for row in pairs.itertuples(index=False)}


sex_choices = _choices(alcohol_df, "sex", "sex_label")
age_choices = _choices(alcohol_df, "age", "age_label")
sex_default = list(sex_choices.values())
age_default = list(age_choices.values())

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_checkbox_group("sex", "Sex", choices=sex_choices, selected=sex_default),
        ui.input_checkbox_group("age", "Age group", choices=age_choices, selected=age_default),
        title="Filter controls",
    ),
    ui.card(
        ui.card_header("Alcohol habits by country"),
        ui.card_body(
            output_widget("alcohol_chart", width="100%", height="100%"),
            class_="p-0",
        ),
    ),
    ui.card(
        ui.card_header("Sex satisfaction level by country"),
        ui.p("Not divided into age groups in this dataset (population aged 16+)."),
        ui.card_body(
            output_widget("satisfaction_chart", width="100%", height="100%"),
            class_="p-0",
        ),
    ),
    ui.card(
        ui.card_header("Alcohol consumption vs sex satisfaction (scatterplot)"),
        ui.card_body(
            output_widget("scatter_chart", width="100%", height="100%"),
            class_="p-0",
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
            document.querySelectorAll('#alcohol_chart, #satisfaction_chart, #scatter_chart, .js-plotly-plot')
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

          watchPlots();
          new MutationObserver(watchPlots).observe(document.body, { childList: true, subtree: true });
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
    @reactive.calc
    def alcohol_selected():
        if alcohol_df.empty:
            return alcohol_df
        data = alcohol_df.copy()
        selected_sex = input.sex()
        selected_age = input.age()
        if selected_sex:
            data = data.loc[data["sex"].isin(selected_sex)]
        if selected_age:
            data = data.loc[data["age"].isin(selected_age)]
        if data.empty:
            return data
        group_cols = ["geo", "frequenc"]
        if "geo_label" in data.columns:
            group_cols.append("geo_label")
        if "frequenc_label" in data.columns:
            group_cols.append("frequenc_label")
        return data.groupby(group_cols, as_index=False)["OBS_VALUE"].mean()

    @reactive.calc
    def satisfaction_country():
        if satisfaction_df.empty:
            return satisfaction_df
        selected_sex = input.sex()
        data = satisfaction_df.copy()
        if selected_sex:
            data = data.loc[data["sex"].isin(selected_sex)]
        if data.empty:
            return data
        country_cols = ["geo"]
        if "geo_label" in data.columns:
            country_cols.append("geo_label")
        grouped = data.groupby(country_cols, as_index=False)["OBS_VALUE"].mean()
        return grouped.sort_values("OBS_VALUE", ascending=False)

    @render_widget
    def alcohol_chart():
        if load_error:
            return _empty_plot(f"Data loading failed: {load_error}")
        data = alcohol_selected()
        if data.empty:
            return _empty_plot("No alcohol data for the selected sex and age group.")

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
            x="alcohol_value",
            y="satisfaction_value",
            hover_name=hover_col,
            labels={
                "alcohol_value": "Alcohol consumption share (%)",
                "satisfaction_value": "Sex satisfaction share (%)",
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
