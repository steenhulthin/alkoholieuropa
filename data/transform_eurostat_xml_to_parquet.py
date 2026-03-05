"""Transform Eurostat SDMX XML files into Parquet tables for Shiny dashboards.

This script is designed for XML payloads from the Eurostat SDMX API.
It always exports dimensions and codelists, and exports observations when
the XML includes data (e.g., GenericData/CompactData payloads).
"""

#from __future__ import annotations

import argparse
import re
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


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


def transform_file(xml_path: Path, output_dir: Path) -> dict[str, Path]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    dataset = _dataset_id(root, xml_path.stem)
    safe_dataset = re.sub(r"[^A-Za-z0-9_]+", "_", dataset).strip("_").lower()

    codelists_df, codelist_labels = _extract_codelists(root, dataset)
    dimensions_df = _extract_dimensions(root, dataset)
    observations_df = _extract_observations(root, dataset)
    observations_labeled_df = _attach_labels(observations_df, dimensions_df, codelist_labels)

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
