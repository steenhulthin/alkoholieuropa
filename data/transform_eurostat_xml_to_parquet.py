"""Transform Eurostat SDMX XML files into Parquet tables for Shiny dashboards.

This script reads local XML structure files from `data/`, writes local Parquet
lookup tables, and ensures observation Parquet files are available for offline
dashboard runtime. If an XML file does not include observations, the script
fetches the dataset values from Eurostat during preprocessing and writes them to
`data/processed/` so the dashboard itself does not need network access.
"""

#from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.request import urlopen
import xml.etree.ElementTree as ET

import pandas as pd

_OBS_RE = re.compile(r"^\s*([-+]?\d*\.?\d+)")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


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


def _name_by_lang(node: ET.Element, lang: str = "en") -> str | None:
    names: dict[str, str] = {}
    for child in node:
        if _local_name(child.tag) != "Name":
            continue
        xml_lang = child.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "")
        text = (child.text or "").strip()
        if text:
            names[xml_lang] = text

    if lang in names:
        return names[lang]
    if names:
        return next(iter(names.values()))
    return None


def _dataset_id(root: ET.Element, fallback: str) -> str:
    dataflow = next((n for n in root.iter() if _local_name(n.tag) == "Dataflow"), None)
    if dataflow is not None and dataflow.attrib.get("id"):
        return dataflow.attrib["id"]

    structure = next((n for n in root.iter() if _local_name(n.tag) == "DataStructure"), None)
    if structure is not None and structure.attrib.get("id"):
        return structure.attrib["id"]

    return fallback


def _load_eurostat_tsv(dataset_id: str) -> pd.DataFrame:
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
    long_df.insert(0, "dataset_id", dataset_id)
    return long_df


def _load_eurostat_json(dataset_id: str) -> pd.DataFrame:
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

        row: dict[str, object] = {"dataset_id": dataset_id, "OBS_VALUE": float(obs_value)}
        for i, dim in enumerate(dim_ids):
            row[dim] = dim_pos_to_code.get(dim, {}).get(positions[i])
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


def _load_eurostat_api(dataset_id: str) -> pd.DataFrame:
    try:
        return _load_eurostat_json(dataset_id)
    except Exception as json_exc:
        try:
            return _load_eurostat_tsv(dataset_id)
        except Exception as tsv_exc:
            raise RuntimeError(
                f"Eurostat load failed for '{dataset_id}'. JSON error: {json_exc}. TSV error: {tsv_exc}."
            ) from tsv_exc


def _extract_codelists(root: ET.Element, dataset_id: str) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    rows: list[dict[str, str]] = []
    label_map: dict[str, dict[str, str]] = {}

    for codelist in root.iter():
        if _local_name(codelist.tag) != "Codelist":
            continue

        codelist_id = codelist.attrib.get("id")
        if not codelist_id:
            continue

        codelist_name = _name_by_lang(codelist, "en") or codelist_id
        label_map[codelist_id] = {}

        for code in codelist:
            if _local_name(code.tag) != "Code":
                continue

            code_id = code.attrib.get("id")
            if not code_id:
                continue

            name_en = _name_by_lang(code, "en") or code_id
            name_de = _name_by_lang(code, "de")
            name_fr = _name_by_lang(code, "fr")

            rows.append(
                {
                    "dataset_id": dataset_id,
                    "codelist_id": codelist_id,
                    "codelist_name": codelist_name,
                    "code": code_id,
                    "label_en": name_en,
                    "label_de": name_de,
                    "label_fr": name_fr,
                }
            )
            label_map[codelist_id][code_id] = name_en

    return pd.DataFrame(rows), label_map


def _extract_dimensions(root: ET.Element, dataset_id: str) -> pd.DataFrame:
    dim_list = next((n for n in root.iter() if _local_name(n.tag) == "DimensionList"), None)
    if dim_list is None:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for dim in dim_list:
        dim_type = _local_name(dim.tag)
        if dim_type not in {"Dimension", "TimeDimension"}:
            continue

        dim_id = dim.attrib.get("id")
        if not dim_id:
            continue

        pos_text = dim.attrib.get("position")
        position = int(pos_text) if pos_text and pos_text.isdigit() else None

        concept_ref = dim.find("./{*}ConceptIdentity/{*}Ref")
        concept_id = concept_ref.attrib.get("id") if concept_ref is not None else dim_id

        enum_ref = dim.find(".//{*}Enumeration/{*}Ref")
        codelist_id = enum_ref.attrib.get("id") if enum_ref is not None else None

        rows.append(
            {
                "dataset_id": dataset_id,
                "dimension_id": dim_id,
                "dimension_type": dim_type,
                "position": position,
                "concept_id": concept_id,
                "codelist_id": codelist_id,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["position", "dimension_id"], na_position="last")
    return df


def _read_value_nodes(node: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in node.iter():
        if _local_name(child.tag) != "Value":
            continue
        key = child.attrib.get("id") or child.attrib.get("concept")
        val = child.attrib.get("value")
        if key and val is not None:
            values[key] = val
    return values


def _parse_obs(obs: ET.Element) -> dict[str, str]:
    row: dict[str, str] = {}

    for key, val in obs.attrib.items():
        if not key.startswith("{"):
            row[key] = val

    for child in obs:
        tag = _local_name(child.tag)
        if tag == "ObsDimension":
            val = child.attrib.get("value")
            if val is not None:
                row.setdefault("TIME_PERIOD", val)
        elif tag == "ObsValue":
            val = child.attrib.get("value")
            if val is not None:
                row["OBS_VALUE"] = val
        elif tag in {"ObsKey", "Attributes", "ObsAttributes", "SeriesKey", "Key"}:
            row.update(_read_value_nodes(child))
        elif tag == "Value":
            key = child.attrib.get("id") or child.attrib.get("concept")
            val = child.attrib.get("value")
            if key and val is not None:
                row[key] = val

    return row


def _extract_observations(root: ET.Element, dataset_id: str) -> pd.DataFrame:
    parent_map = {child: parent for parent in root.iter() for child in parent}
    rows: list[dict[str, str]] = []

    for series in root.iter():
        if _local_name(series.tag) != "Series":
            continue
        series_values: dict[str, str] = {}
        for child in series:
            if _local_name(child.tag) in {"SeriesKey", "Key"}:
                series_values.update(_read_value_nodes(child))

        for child in series:
            if _local_name(child.tag) != "Obs":
                continue
            row = series_values.copy()
            row.update(_parse_obs(child))
            rows.append(row)

    for obs in root.iter():
        if _local_name(obs.tag) != "Obs":
            continue
        parent = parent_map.get(obs)
        if parent is not None and _local_name(parent.tag) == "Series":
            continue
        rows.append(_parse_obs(obs))

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.insert(0, "dataset_id", dataset_id)

    if "OBS_VALUE" in df.columns:
        df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")

    if "TIME_PERIOD" in df.columns:
        year_text = df["TIME_PERIOD"].astype(str).str.extract(r"^(\d{4})")[0]
        df["year"] = pd.to_numeric(year_text, errors="coerce").astype("Int64")

    return df


def _attach_labels(
    observations: pd.DataFrame, dimensions: pd.DataFrame, codelist_labels: dict[str, dict[str, str]]
) -> pd.DataFrame:
    if observations.empty or dimensions.empty:
        return observations

    df = observations.copy()
    for dim in dimensions.itertuples(index=False):
        dim_id = getattr(dim, "dimension_id")
        codelist_id = getattr(dim, "codelist_id")
        if not codelist_id or dim_id not in df.columns:
            continue

        labels = codelist_labels.get(codelist_id, {})
        if not labels:
            continue
        df[f"{dim_id}_label"] = df[dim_id].map(labels).fillna(df[dim_id])

    for attr_col, codelist_id in (("OBS_FLAG", "OBS_FLAG"), ("CONF_STATUS", "CONF_STATUS")):
        if attr_col in df.columns and codelist_id in codelist_labels:
            labels = codelist_labels[codelist_id]
            df[f"{attr_col}_label"] = df[attr_col].map(labels).fillna(df[attr_col])

    return df


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    try:
        df.to_parquet(path, index=False)
    except Exception as exc:
        raise RuntimeError(
            "Failed to write Parquet. Install a Parquet engine such as pyarrow: pip install pyarrow"
        ) from exc


def _apply_project_filters(
    dataset_id: str, observations_df: pd.DataFrame, codelists_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply project-specific row exclusions during preprocessing."""
    filtered_obs = observations_df.copy()
    filtered_codelists = codelists_df.copy()

    eu_geo_codes = {"EU27_2020", "EU28", "EU27_2007"}
    unwanted_freq_codes = {"NEVER", "N12M"}
    unwanted_freq_labels = {"never", "not in the last 12 months"}
    allowed_alcohol_age_codes = {"Y15-24", "Y25-34", "Y35-44", "Y45-64", "Y65-74", "Y_GE75"}
    removed_sex_codes = {"T"}
    removed_satisfaction_level_codes = {"EURO"}

    if not filtered_obs.empty:
        if "geo" in filtered_obs.columns:
            geo_codes = filtered_obs["geo"].astype(str).str.strip().str.upper()
            is_eu = geo_codes.isin(eu_geo_codes)
            is_euro_area = geo_codes.str.match(r"^EA\d+$", na=False)
            filtered_obs = filtered_obs.loc[~(is_eu | is_euro_area)]
        if "geo_label" in filtered_obs.columns:
            geo_text = filtered_obs["geo_label"].astype(str).str.lower()
            filtered_obs = filtered_obs.loc[
                ~(
                    geo_text.str.contains("european union", na=False)
                    | geo_text.str.contains("euro area", na=False)
                )
            ]
        if "sex" in filtered_obs.columns:
            filtered_obs = filtered_obs.loc[~filtered_obs["sex"].isin(removed_sex_codes)]

        if dataset_id.upper() == "HLTH_EHIS_AL1C":
            if "age" in filtered_obs.columns:
                filtered_obs = filtered_obs.loc[filtered_obs["age"].isin(allowed_alcohol_age_codes)]
            if "frequenc" in filtered_obs.columns:
                freq_codes = filtered_obs["frequenc"].astype(str).str.strip().str.upper()
                filtered_obs = filtered_obs.loc[~freq_codes.isin(unwanted_freq_codes)]
            if "frequenc_label" in filtered_obs.columns:
                freq_labels = filtered_obs["frequenc_label"].astype(str).str.strip().str.lower()
                filtered_obs = filtered_obs.loc[~freq_labels.isin(unwanted_freq_labels)]
        if dataset_id.upper() == "SDG_03_20":
            if "levels" in filtered_obs.columns:
                level_codes = filtered_obs["levels"].astype(str).str.strip().str.upper()
                filtered_obs = filtered_obs.loc[~level_codes.isin(removed_satisfaction_level_codes)]
            if "levels_label" in filtered_obs.columns:
                level_labels = filtered_obs["levels_label"].astype(str).str.strip().str.upper()
                filtered_obs = filtered_obs.loc[~level_labels.isin(removed_satisfaction_level_codes)]

    if not filtered_codelists.empty:
        is_geo = filtered_codelists["codelist_id"].eq("GEO")
        if is_geo.any():
            geo_codes = filtered_codelists["code"].astype(str).str.strip().str.upper()
            geo_labels = filtered_codelists["label_en"].astype(str).str.lower()
            remove_geo = is_geo & (
                geo_codes.isin(eu_geo_codes)
                | geo_codes.str.match(r"^EA\d+$", na=False)
                | geo_labels.str.contains("european union", na=False)
                | geo_labels.str.contains("euro area", na=False)
            )
            filtered_codelists = filtered_codelists.loc[~remove_geo]
        is_age = filtered_codelists["codelist_id"].eq("AGE")
        if dataset_id.upper() == "HLTH_EHIS_AL1C" and is_age.any():
            remove_age = is_age & (~filtered_codelists["code"].isin(allowed_alcohol_age_codes))
            filtered_codelists = filtered_codelists.loc[~remove_age]
        is_sex = filtered_codelists["codelist_id"].eq("SEX")
        if is_sex.any():
            sex_labels = filtered_codelists["label_en"].astype(str).str.strip().str.lower()
            remove_sex = is_sex & (
                filtered_codelists["code"].isin(removed_sex_codes) | sex_labels.eq("total")
            )
            filtered_codelists = filtered_codelists.loc[~remove_sex]

        if dataset_id.upper() == "HLTH_EHIS_AL1C":
            is_freq = filtered_codelists["codelist_id"].eq("FREQUENC")
            if is_freq.any():
                freq_labels = filtered_codelists["label_en"].astype(str).str.strip().str.lower()
                remove_freq = is_freq & (
                    filtered_codelists["code"].isin(unwanted_freq_codes) | freq_labels.isin(unwanted_freq_labels)
                )
                filtered_codelists = filtered_codelists.loc[~remove_freq]
        if dataset_id.upper() == "SDG_03_20":
            is_levels = filtered_codelists["codelist_id"].eq("LEVELS")
            if is_levels.any():
                level_labels = filtered_codelists["label_en"].astype(str).str.strip().str.upper()
                remove_levels = is_levels & (
                    filtered_codelists["code"].isin(removed_satisfaction_level_codes)
                    | level_labels.isin(removed_satisfaction_level_codes)
                )
                filtered_codelists = filtered_codelists.loc[~remove_levels]

    return filtered_obs, filtered_codelists


def transform_file(xml_path: Path, output_dir: Path) -> dict[str, Path]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    dataset = _dataset_id(root, xml_path.stem)
    safe_dataset = re.sub(r"[^A-Za-z0-9_]+", "_", dataset).strip("_").lower()

    codelists_df, codelist_labels = _extract_codelists(root, dataset)
    dimensions_df = _extract_dimensions(root, dataset)
    observations_df = _extract_observations(root, dataset)
    if observations_df.empty:
        observations_df = _load_eurostat_api(dataset)
    observations_labeled_df = _attach_labels(observations_df, dimensions_df, codelist_labels)
    observations_labeled_df, codelists_df = _apply_project_filters(
        dataset, observations_labeled_df, codelists_df
    )
    if observations_labeled_df.empty:
        raise RuntimeError(
            f"No observation rows were produced for dataset '{dataset}'. "
            "The dashboard needs local __observations.parquet files for every runtime dataset."
        )

    output_paths: dict[str, Path] = {}

    if not codelists_df.empty:
        p = output_dir / f"{safe_dataset}__codelists.parquet"
        _write_parquet(codelists_df, p)
        output_paths["codelists"] = p

    if not dimensions_df.empty:
        p = output_dir / f"{safe_dataset}__dimensions.parquet"
        _write_parquet(dimensions_df, p)
        output_paths["dimensions"] = p

    if not observations_labeled_df.empty:
        p = output_dir / f"{safe_dataset}__observations.parquet"
        _write_parquet(observations_labeled_df, p)
        output_paths["observations"] = p

    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Directory containing Eurostat XML files (default: script directory).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "processed",
        help="Directory where Parquet files are written (default: data/processed).",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    xml_files = sorted(input_dir.glob("*.xml"))
    if not xml_files:
        raise FileNotFoundError(f"No XML files found in {input_dir}")

    print(f"Found {len(xml_files)} XML file(s) in {input_dir}")
    for xml_file in xml_files:
        paths = transform_file(xml_file, output_dir)
        if paths:
            print(f"\n{xml_file.name}")
            for table_name, path in paths.items():
                print(f"  - {table_name}: {path}")
        else:
            print(f"\n{xml_file.name}\n  - No extractable tables found.")


if __name__ == "__main__":
    main()
