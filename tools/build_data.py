#!/usr/bin/env python3
"""Build embedded steam_data arrays from immutable canonical CSV + schema.

This script never rewrites canonical CSV content.
"""

import argparse
import csv
import json
import os
import pprint

def to_float(value, field_name, path, row_idx):
    if value is None:
        raise ValueError(
            "invalid float in {} row {} field {}: {}".format(path, row_idx, field_name, value)
        )
    cleaned = str(value).strip().replace(",", "").replace(" ", "")
    if cleaned == "":
        raise ValueError(
            "invalid float in {} row {} field {}: {}".format(path, row_idx, field_name, value)
        )
    return float(cleaned)


def _parse_numeric_text(value):
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", "").replace(" ", "")
    if cleaned == "":
        return None
    try:
        float(cleaned)
        return cleaned
    except Exception:
        return None


def decimals_in_text(value):
    numeric = _parse_numeric_text(value)
    if numeric is None:
        return None

    if "e" in numeric or "E" in numeric:
        base = numeric.split("e")[0].split("E")[0]
    else:
        base = numeric
    if "." not in base:
        return 0
    return len(base.split(".")[1])


def compute_text_precision(rows, semantic_to_column):
    precision = {}
    for semantic, column in semantic_to_column.items():
        max_decimals = 0
        for row in rows:
            if column not in row:
                continue
            d = decimals_in_text(row.get(column))
            if d is not None and d > max_decimals:
                max_decimals = d
        precision[semantic] = max_decimals
    return precision


def merge_precision(base, update):
    for key, value in update.items():
        value = float(value)
        if key not in base or value > base[key]:
            base[key] = value


def finalize_precision(raw):
    out = dict(raw)
    out["P_kPa"] = max(out.get("P_kPa", 2), out.get("P", 0))
    out["T_C"] = max(out.get("T_C", 2), out.get("T", 0))
    out["v"] = max(out.get("v", 6), out.get("vf", 0), out.get("vg", 0))
    out["u"] = max(out.get("u", 2), out.get("uf", 0), out.get("ug", 0))
    out["h"] = max(out.get("h", 2), out.get("hf", 0), out.get("hg", 0))
    out["s"] = max(out.get("s", 4), out.get("sf", 0), out.get("sg", 0))
    out["x"] = max(4, min(6, out.get("x", 6)))

    keep = {
        "P_kPa",
        "T_C",
        "v",
        "u",
        "h",
        "s",
        "x",
        "vf",
        "vg",
        "uf",
        "ug",
        "hf",
        "hg",
        "sf",
        "sg",
    }
    filtered = {}
    for key in keep:
        if key in out:
            filtered[key] = out[key]

    order = ["P_kPa", "T_C", "v", "u", "h", "s", "x", "vf", "vg", "uf", "ug", "hf", "hg", "sf", "sg"]
    ordered = {}
    for key in order:
        if key in filtered:
            ordered[key] = filtered[key]
    return ordered


def read_csv_rows(path):
    if not os.path.exists(path):
        raise FileNotFoundError("missing canonical CSV: " + path)
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        headers = list(reader.fieldnames or [])
    return headers, rows


def load_schema(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    out = {}
    for item in data.get("tables", []):
        table_name = item.get("table")
        if table_name:
            out[table_name] = item
    return out


def require_schema_entry(schema, table_name):
    entry = schema.get(table_name)
    if entry is None:
        raise ValueError("missing schema entry for table {}".format(table_name))
    if not entry.get("file"):
        raise ValueError("schema entry for {} must define file".format(table_name))
    return entry


def resolve_columns(table_name, headers, schema_entry, required_props):
    columns = {}
    p_col = schema_entry.get("pressure_column")
    t_col = schema_entry.get("temperature_column")
    col_map = schema_entry.get("columns") or {}

    if p_col is None or t_col is None:
        raise ValueError("schema mapping for {} must include pressure_column and temperature_column".format(table_name))

    columns["pressure"] = p_col
    columns["temperature"] = t_col

    for prop in required_props:
        mapped = col_map.get(prop)
        if mapped is None:
            raise ValueError("schema mapping for {} missing required property '{}'".format(table_name, prop))
        columns[prop] = mapped

    missing_headers = []
    for key, column in columns.items():
        if column not in headers:
            missing_headers.append("{}->{}".format(key, column))
    if missing_headers:
        raise ValueError("missing CSV headers for {}: {}".format(table_name, ", ".join(missing_headers)))
    return columns


def parse_saturation_table(table_name, path, schema_entry, axis):
    headers, rows = read_csv_rows(path)
    cols = resolve_columns(
        table_name=table_name,
        headers=headers,
        schema_entry=schema_entry,
        required_props=["vf", "vg", "uf", "ug", "hf", "hg", "sf", "sg"],
    )

    precision = compute_text_precision(
        rows,
        {
            "T_C": cols["temperature"],
            "P_kPa": cols["pressure"],
            "vf": cols["vf"],
            "vg": cols["vg"],
            "uf": cols["uf"],
            "ug": cols["ug"],
            "hf": cols["hf"],
            "hg": cols["hg"],
            "sf": cols["sf"],
            "sg": cols["sg"],
        },
    )

    parsed = []
    skipped_rows = []
    for row_idx, row in enumerate(rows, start=2):
        try:
            item = {
                "T": to_float(row.get(cols["temperature"]), "temperature", path, row_idx),
                "P": to_float(row.get(cols["pressure"]), "pressure", path, row_idx),
                "vf": to_float(row.get(cols["vf"]), "vf", path, row_idx),
                "vg": to_float(row.get(cols["vg"]), "vg", path, row_idx),
                "uf": to_float(row.get(cols["uf"]), "uf", path, row_idx),
                "ug": to_float(row.get(cols["ug"]), "ug", path, row_idx),
                "hf": to_float(row.get(cols["hf"]), "hf", path, row_idx),
                "hg": to_float(row.get(cols["hg"]), "hg", path, row_idx),
                "sf": to_float(row.get(cols["sf"]), "sf", path, row_idx),
                "sg": to_float(row.get(cols["sg"]), "sg", path, row_idx),
            }
            parsed.append(item)
        except Exception:
            skipped_rows.append(row_idx)

    if axis == "T":
        parsed.sort(key=lambda x: x["T"])
    elif axis == "P":
        parsed.sort(key=lambda x: x["P"])
    else:
        raise ValueError("invalid saturation axis: {}".format(axis))

    out = {
        "T": [r["T"] for r in parsed],
        "P": [r["P"] for r in parsed],
        "vf": [r["vf"] for r in parsed],
        "vg": [r["vg"] for r in parsed],
        "uf": [r["uf"] for r in parsed],
        "ug": [r["ug"] for r in parsed],
        "hf": [r["hf"] for r in parsed],
        "hg": [r["hg"] for r in parsed],
        "sf": [r["sf"] for r in parsed],
        "sg": [r["sg"] for r in parsed],
    }

    stats = {
        "table": table_name,
        "file": path,
        "rows_total": len(rows),
        "rows_parsed": len(parsed),
        "rows_skipped": len(skipped_rows),
        "skipped_row_numbers": skipped_rows,
    }
    stats["precision_text"] = dict(precision)
    return out, stats, precision


def parse_piecewise_table(table_name, path, schema_entry):
    headers, rows = read_csv_rows(path)
    cols = resolve_columns(
        table_name=table_name,
        headers=headers,
        schema_entry=schema_entry,
        required_props=["v", "u", "h", "s"],
    )

    precision = compute_text_precision(
        rows,
        {
            "P_kPa": cols["pressure"],
            "T_C": cols["temperature"],
            "v": cols["v"],
            "u": cols["u"],
            "h": cols["h"],
            "s": cols["s"],
        },
    )

    block_map = {}
    skipped_rows = []
    parsed_rows = 0

    for row_idx, row in enumerate(rows, start=2):
        try:
            p = to_float(row.get(cols["pressure"]), "pressure", path, row_idx)
            t = to_float(row.get(cols["temperature"]), "temperature", path, row_idx)
            v = to_float(row.get(cols["v"]), "v", path, row_idx)
            u = to_float(row.get(cols["u"]), "u", path, row_idx)
            h = to_float(row.get(cols["h"]), "h", path, row_idx)
            s = to_float(row.get(cols["s"]), "s", path, row_idx)
        except Exception:
            skipped_rows.append(row_idx)
            continue

        if p not in block_map:
            block_map[p] = {
                "T": [],
                "v": [],
                "u": [],
                "h": [],
                "s": [],
            }
        block_map[p]["T"].append(t)
        block_map[p]["v"].append(v)
        block_map[p]["u"].append(u)
        block_map[p]["h"].append(h)
        block_map[p]["s"].append(s)
        parsed_rows += 1

    # Sort each pressure block by temperature while preserving per-row values.
    pressures = sorted(block_map.keys())
    t_by_p = []
    v_by_p = []
    u_by_p = []
    h_by_p = []
    s_by_p = []
    row_counts_by_p = []
    for p in pressures:
        zipped = list(
            zip(
                block_map[p]["T"],
                block_map[p]["v"],
                block_map[p]["u"],
                block_map[p]["h"],
                block_map[p]["s"],
            )
        )
        zipped.sort(key=lambda x: x[0])
        row_counts_by_p.append(len(zipped))

        t_by_p.append([x[0] for x in zipped])
        v_by_p.append([x[1] for x in zipped])
        u_by_p.append([x[2] for x in zipped])
        h_by_p.append([x[3] for x in zipped])
        s_by_p.append([x[4] for x in zipped])

    out = {
        "P": pressures,
        "T_by_P": t_by_p,
        "u_by_P": u_by_p,
        "h_by_P": h_by_p,
        "v_by_P": v_by_p,
        "s_by_P": s_by_p,
    }

    stats = {
        "table": table_name,
        "file": path,
        "rows_total": len(rows),
        "rows_parsed": parsed_rows,
        "rows_skipped": len(skipped_rows),
        "skipped_row_numbers": skipped_rows,
        "pressure_blocks": len(pressures),
        "row_counts_by_p": row_counts_by_p,
    }
    stats["precision_text"] = dict(precision)
    return out, stats, precision


def write_steam_data(path, sat_t, sat_p, sh, comp, precision):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    text = []
    text.append('"""Auto-generated steam lookup data.\n')
    text.append("Generated by tools/build_data.py from immutable canonical CSV tables.\n")
    text.append('"""\n\n')

    text.append("SAT_T = ")
    text.append(pprint.pformat(sat_t, width=100, sort_dicts=False))
    text.append("\n\n")

    text.append("SAT_P = ")
    text.append(pprint.pformat(sat_p, width=100, sort_dicts=False))
    text.append("\n\n")

    text.append("SH = ")
    text.append(pprint.pformat(sh, width=100, sort_dicts=False))
    text.append("\n\n")

    text.append("COMP = ")
    text.append(pprint.pformat(comp, width=100, sort_dicts=False))
    text.append("\n\n")

    text.append("PRECISION = ")
    text.append(pprint.pformat(precision, width=100, sort_dicts=False))
    text.append("\n")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join(text))


def write_build_report(path, sat_t_stats, sat_p_stats, sh_stats, comp_stats, precision):
    lines = []
    lines.append("XSteam-Lite Build Report")
    lines.append("")

    for stats in (sat_t_stats, sat_p_stats, sh_stats, comp_stats):
        lines.append("{} ({})".format(stats["table"], stats["file"]))
        lines.append("  rows_total={}".format(stats["rows_total"]))
        lines.append("  rows_parsed={}".format(stats["rows_parsed"]))
        lines.append("  rows_skipped={}".format(stats["rows_skipped"]))
        if stats["rows_skipped"] > 0:
            lines.append("  skipped_row_numbers={}".format(stats["skipped_row_numbers"]))
        if "pressure_blocks" in stats:
            lines.append("  pressure_blocks={}".format(stats["pressure_blocks"]))
            lines.append("  block_row_counts={}".format(stats["row_counts_by_p"]))
        if "precision_text" in stats:
            lines.append("  precision_text={}".format(stats["precision_text"]))
        lines.append("")

    lines.append("PRECISION (display metadata)")
    lines.append("  {}".format(precision))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")


def main():
    parser = argparse.ArgumentParser(description="Build steam_data.py from canonical CSV + schema")
    parser.add_argument("--csv-dir", default="data/canonical_csv", help="Immutable canonical CSV directory")
    parser.add_argument("--schema", default="data/schema.json", help="Schema mapping JSON")
    parser.add_argument("--output", default="data/steam_data.py", help="Output data module")
    parser.add_argument("--report", default="data/build_report.txt", help="Build report output path")
    args = parser.parse_args()

    schema = load_schema(args.schema)

    a1_spec = require_schema_entry(schema, "A1")
    a2_spec = require_schema_entry(schema, "A2")
    a3_spec = require_schema_entry(schema, "A3")
    a4_spec = require_schema_entry(schema, "A4")

    a1_path = os.path.join(args.csv_dir, a1_spec["file"])
    a2_path = os.path.join(args.csv_dir, a2_spec["file"])
    a3_path = os.path.join(args.csv_dir, a3_spec["file"])
    a4_path = os.path.join(args.csv_dir, a4_spec["file"])

    sat_t, sat_t_stats, sat_t_precision = parse_saturation_table("A1", a1_path, a1_spec, axis="T")
    precision_raw = {}
    merge_precision(precision_raw, sat_t_precision)

    sat_p, sat_p_stats, sat_p_precision = parse_saturation_table("A2", a2_path, a2_spec, axis="P")
    sat_p_stats["table"] = "A2"
    merge_precision(precision_raw, sat_p_precision)

    sh, sh_stats, sh_precision = parse_piecewise_table("A3", a3_path, a3_spec)
    comp, comp_stats, comp_precision = parse_piecewise_table("A4", a4_path, a4_spec)
    merge_precision(precision_raw, sh_precision)
    merge_precision(precision_raw, comp_precision)

    precision = finalize_precision(precision_raw)

    write_steam_data(args.output, sat_t=sat_t, sat_p=sat_p, sh=sh, comp=comp, precision=precision)
    write_build_report(
        args.report,
        sat_t_stats=sat_t_stats,
        sat_p_stats=sat_p_stats,
        sh_stats=sh_stats,
        comp_stats=comp_stats,
        precision=precision,
    )

if __name__ == "__main__":
    main()
