from __future__ import annotations

import re
import json
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

app_dir = Path(__file__).parent
project_root = app_dir.parent
data_dir = project_root / "data"
processed_dir = data_dir / "processed"

_OBS_RE = re.compile(r"^\s*([-+]?\d*\.?\d+)")


def _parse_obs_value(value: object) -> float | None:
    if pd.isna(value):
        return None
    match = _OBS_RE.search(str(value))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def load_eurostat_tsv(dataset_id: str) -> pd.DataFrame:
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset_id}?format=TSV"
    raw = pd.read_csv(url, sep="\t")

    first_col = raw.columns[0]
    dim_part, _ = first_col.split("\\", 1)
    dim_names = dim_part.split(",")

    table = raw.rename(columns={first_col: "_dims"})
    dim_values = table["_dims"].str.split(",", expand=True)
    dim_values.columns = dim_names

    table = pd.concat([dim_values, table.drop(columns="_dims")], axis=1)
    year_cols = [col for col in table.columns if re.match(r"^\d{4}", str(col))]
    long_df = table.melt(
        id_vars=dim_names,
        value_vars=year_cols,
        var_name="TIME_PERIOD",
        value_name="raw_value",
    )
    long_df["year"] = pd.to_numeric(
        long_df["TIME_PERIOD"].astype(str).str.extract(r"(\d{4})")[0], errors="coerce"
    ).astype("Int64")
    long_df["OBS_VALUE"] = long_df["raw_value"].map(_parse_obs_value)
    long_df = long_df.dropna(subset=["year", "OBS_VALUE"])
    return long_df


def load_eurostat_json(dataset_id: str) -> pd.DataFrame:
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset_id}"
    with urlopen(url) as response:
        data = json.loads(response.read().decode("utf-8"))

    dim_ids = data.get("id", [])
    dim_sizes = data.get("size", [])
    dimensions = data.get("dimension", {})
    values = data.get("value", {})

    if not dim_ids or not dim_sizes or not isinstance(values, dict):
        return pd.DataFrame()

    dim_pos_to_code: dict[str, dict[int, str]] = {}
    for dim in dim_ids:
        cat = ((dimensions.get(dim) or {}).get("category") or {})
        idx = cat.get("index", {}) or {}
        dim_pos_to_code[dim] = {int(pos): code for code, pos in idx.items()}

    rows: list[dict[str, object]] = []
    for flat_index_str, obs_value in values.items():
        flat_index = int(flat_index_str)
        positions: list[int] = []
        remainder = flat_index
        for size in reversed(dim_sizes):
            positions.append(remainder % size)
            remainder //= size
        positions.reverse()

        row: dict[str, object] = {"OBS_VALUE": float(obs_value)}
        for i, dim in enumerate(dim_ids):
            pos = positions[i]
            row[dim] = dim_pos_to_code.get(dim, {}).get(pos)
        rows.append(row)

    df = pd.DataFrame(rows)
    if "time" in df.columns:
        df = df.rename(columns={"time": "TIME_PERIOD"})
    if "TIME_PERIOD" in df.columns:
        df["year"] = pd.to_numeric(
            df["TIME_PERIOD"].astype(str).str.extract(r"(\d{4})")[0], errors="coerce"
        ).astype("Int64")
        df = df.dropna(subset=["year"])
    return df


def load_eurostat(dataset_id: str) -> pd.DataFrame:
    try:
        return load_eurostat_json(dataset_id)
    except Exception as json_exc:
        try:
            return load_eurostat_tsv(dataset_id)
        except Exception as tsv_exc:
            raise RuntimeError(
                f"Eurostat load failed for '{dataset_id}'. JSON error: {json_exc}. TSV error: {tsv_exc}."
            ) from tsv_exc


def attach_labels(df: pd.DataFrame, dataset_id: str) -> pd.DataFrame:
    dimensions_path = processed_dir / f"{dataset_id}__dimensions.parquet"
    codelists_path = processed_dir / f"{dataset_id}__codelists.parquet"
    if not dimensions_path.exists() or not codelists_path.exists() or df.empty:
        return df

    dimensions = pd.read_parquet(dimensions_path)
    codelists = pd.read_parquet(codelists_path)
    dim_to_codelist = (
        dimensions.dropna(subset=["dimension_id", "codelist_id"])
        .set_index("dimension_id")["codelist_id"]
        .to_dict()
    )

    labeled = df.copy()
    for dim, codelist_id in dim_to_codelist.items():
        if dim not in labeled.columns:
            continue
        lookup = (
            codelists.loc[codelists["codelist_id"] == codelist_id, ["code", "label_en"]]
            .drop_duplicates(subset=["code"])
            .set_index("code")["label_en"]
            .to_dict()
        )
        labeled[f"{dim}_label"] = labeled[dim].map(lookup).fillna(labeled[dim])

    return labeled


def filter_reference_slice(df: pd.DataFrame, keep_dims: list[str]) -> pd.DataFrame:
    constrained = df.copy()
    preferred_values = {
        "freq": "A",
        "unit": "PC",
        "citizen": "TOTAL",
        "quantile": "TOTAL",
    }
    for col in ["freq", "unit", "citizen", "quantile", "levels"]:
        if col not in constrained.columns or col in keep_dims:
            continue
        preferred = preferred_values.get(col)
        if preferred is not None and (constrained[col] == preferred).any():
            constrained = constrained.loc[constrained[col] == preferred]
            continue
        mode = constrained[col].mode(dropna=True)
        if len(mode):
            constrained = constrained.loc[constrained[col] == mode.iloc[0]]
    return constrained


def latest_snapshot(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    ordered = df.sort_values(["year"])
    return ordered.groupby(group_cols, dropna=False, as_index=False).tail(1)
