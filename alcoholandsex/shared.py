from __future__ import annotations

import re
from pathlib import Path

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


def _dataset_basename(dataset_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", dataset_id).strip("_").lower()


def load_eurostat(dataset_id: str) -> pd.DataFrame:
    observations_path = processed_dir / f"{_dataset_basename(dataset_id)}__observations.parquet"
    if not observations_path.exists():
        raise RuntimeError(
            f"Local dataset file is missing: {observations_path}. "
            "Run .\\run_data.ps1 to generate local observation Parquet files before starting the app."
        )

    df = pd.read_parquet(observations_path)
    if df.empty:
        raise RuntimeError(f"Local dataset file is empty: {observations_path}")
    return df


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
        valid_codes = set(
            codelists.loc[codelists["codelist_id"] == codelist_id, "code"].dropna().astype(str).tolist()
        )
        if valid_codes:
            labeled = labeled.loc[labeled[dim].astype(str).isin(valid_codes)]
        lookup = (
            codelists.loc[codelists["codelist_id"] == codelist_id, ["code", "label_en"]]
            .drop_duplicates(subset=["code"])
            .set_index("code")["label_en"]
            .to_dict()
        )
        labeled[f"{dim}_label"] = labeled[dim].map(lookup).fillna(labeled[dim])

    return labeled


def display_label(code: object, label: object, kind: str) -> str:
    code_text = str(code).strip().upper()
    label_text = str(label).strip()
    normalized = label_text.lower()

    if kind == "sex":
        if code_text == "F" or "female" in normalized or "women" in normalized:
            return "Female"
        if code_text == "M" or "male" in normalized or "men" in normalized:
            return "Male"

    if kind == "age":
        age_map = {
            "Y15-24": "15-24",
            "Y25-34": "25-34",
            "Y35-44": "35-44",
            "Y45-64": "45-64",
            "Y65-74": "65-74",
            "Y_GE75": "Over 74",
            "T_GE75": "Over 74",
        }
        if code_text in age_map:
            return age_map[code_text]

    if kind == "frequency":
        if "every day" in normalized or "daily" in normalized:
            return "Daily"
        if "every week" in normalized or "weekly" in normalized or normalized == "week":
            return "Weekly"
        if "every month" in normalized or "monthly" in normalized or normalized == "month":
            return "Monthly"
        if "less" in normalized and "month" in normalized:
            return "Less than monthly"
        if "never" in normalized or "last 12" in normalized:
            return "Never or less than yearly"

    return label_text


def normalize_display_labels(
    df: pd.DataFrame,
    label_specs: list[tuple[str, str, str]],
) -> pd.DataFrame:
    if df.empty:
        return df

    normalized = df.copy()
    for code_col, label_col, kind in label_specs:
        if code_col not in normalized.columns:
            continue
        labels = normalized[label_col] if label_col in normalized.columns else normalized[code_col]
        normalized[label_col] = [
            display_label(code, label, kind)
            for code, label in zip(normalized[code_col], labels)
        ]
    return normalized


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
