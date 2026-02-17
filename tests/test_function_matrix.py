"""Function-matrix and CSV-preservation tests for XSteam-Lite."""

import csv
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import steam_data  # noqa: E402
from tinspire import steam  # noqa: E402


def f(value):
    return float(str(value).strip().replace(",", "").replace(" ", ""))


def tok(value):
    return "{:.10g}".format(float(value))


def assert_close(actual, expected, tol):
    assert abs(actual - expected) <= tol, "actual={} expected={} tol={}".format(actual, expected, tol)


def load_schema_table(table_name):
    with open(os.path.join(ROOT, "data/schema.json"), "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    for entry in schema.get("tables", []):
        if entry.get("table") == table_name:
            return entry
    raise AssertionError("missing schema entry for {}".format(table_name))


def parse_piecewise_csv(table_name):
    entry = load_schema_table(table_name)
    path = os.path.join(ROOT, "data/canonical_csv", entry["file"])
    p_col = entry["pressure_column"]
    t_col = entry["temperature_column"]
    cols = entry["columns"]

    total_rows = 0
    parsed_rows = []
    counts_by_p = {}
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_rows += 1
            try:
                p = f(row[p_col])
                t = f(row[t_col])
                v = f(row[cols["v"]])
                u = f(row[cols["u"]])
                h = f(row[cols["h"]])
                s = f(row[cols["s"]])
            except Exception:
                continue

            parsed_rows.append((p, t, v, u, h, s))
            p_key = tok(p)
            counts_by_p[p_key] = counts_by_p.get(p_key, 0) + 1

    return {
        "path": path,
        "total_rows": total_rows,
        "parsed_rows": parsed_rows,
        "counts_by_p": counts_by_p,
    }


def parse_sat_csv(table_name):
    entry = load_schema_table(table_name)
    path = os.path.join(ROOT, "data/canonical_csv", entry["file"])
    p_col = entry["pressure_column"]
    t_col = entry["temperature_column"]
    cols = entry["columns"]

    total_rows = 0
    parsed_rows = []
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_rows += 1
            try:
                item = (
                    f(row[t_col]),
                    f(row[p_col]),
                    f(row[cols["vf"]]),
                    f(row[cols["vg"]]),
                    f(row[cols["uf"]]),
                    f(row[cols["ug"]]),
                    f(row[cols["hf"]]),
                    f(row[cols["hg"]]),
                    f(row[cols["sf"]]),
                    f(row[cols["sg"]]),
                )
            except Exception:
                continue
            parsed_rows.append(item)

    return {"path": path, "total_rows": total_rows, "parsed_rows": parsed_rows}


def runtime_tuple_set_piecewise(region):
    out = set()
    for i, p in enumerate(region["P"]):
        for j, t in enumerate(region["T_by_P"][i]):
            out.add(
                (
                    tok(p),
                    tok(t),
                    tok(region["v_by_P"][i][j]),
                    tok(region["u_by_P"][i][j]),
                    tok(region["h_by_P"][i][j]),
                    tok(region["s_by_P"][i][j]),
                )
            )
    return out


def sample_indices(length):
    if length <= 1:
        return [0]
    items = [0, length // 2, length - 1]
    return sorted(set(items))


def test_no_rows_dropped_and_block_lengths_match():
    for table_name, runtime in (("A3", steam_data.SH), ("A4", steam_data.COMP)):
        parsed = parse_piecewise_csv(table_name)
        parsed_total = len(parsed["parsed_rows"])
        runtime_total = sum(len(x) for x in runtime["T_by_P"])

        assert parsed_total == runtime_total, "{} parsed_total={} runtime_total={}".format(
            table_name, parsed_total, runtime_total
        )
        assert parsed_total == parsed["total_rows"], "{} has skipped rows in parser".format(table_name)

        runtime_counts = {}
        for i, p in enumerate(runtime["P"]):
            runtime_counts[tok(p)] = len(runtime["T_by_P"][i])

        assert parsed["counts_by_p"] == runtime_counts, "{} block counts mismatch".format(table_name)


def test_random_spot_checks_match_csv_text():
    rng = random.Random(20260217)

    # A3/A4 spot checks (25 each)
    for table_name, runtime in (("A3", steam_data.SH), ("A4", steam_data.COMP)):
        parsed = parse_piecewise_csv(table_name)["parsed_rows"]
        samples = rng.sample(parsed, min(25, len(parsed)))
        runtime_set = runtime_tuple_set_piecewise(runtime)

        for p, t, v, u, h, s in samples:
            key = (tok(p), tok(t), tok(v), tok(u), tok(h), tok(s))
            assert key in runtime_set, "{} missing sampled tuple {}".format(table_name, key)

    # A1 saturation spot checks
    a1 = parse_sat_csv("A1")["parsed_rows"]
    a1_samples = rng.sample(a1, min(25, len(a1)))
    sat_set = set(
        (
            tok(steam_data.SAT_T["T"][i]),
            tok(steam_data.SAT_T["P"][i]),
            tok(steam_data.SAT_T["vf"][i]),
            tok(steam_data.SAT_T["vg"][i]),
            tok(steam_data.SAT_T["uf"][i]),
            tok(steam_data.SAT_T["ug"][i]),
            tok(steam_data.SAT_T["hf"][i]),
            tok(steam_data.SAT_T["hg"][i]),
            tok(steam_data.SAT_T["sf"][i]),
            tok(steam_data.SAT_T["sg"][i]),
        )
        for i in range(len(steam_data.SAT_T["T"]))
    )
    for row in a1_samples:
        key = tuple(tok(x) for x in row)
        assert key in sat_set, "A1 missing sampled tuple {}".format(key)


def test_grid_node_exactness():
    sh_checked = 0
    for i in sample_indices(len(steam_data.SH["P"])):
        p = steam_data.SH["P"][i]
        j = len(steam_data.SH["T_by_P"][i]) - 1
        t = steam_data.SH["T_by_P"][i][j]
        if steam.region_pT(p, t) != "superheated":
            continue
        assert_close(steam.u_pT(p, t), steam_data.SH["u_by_P"][i][j], 1e-9)
        assert_close(steam.h_pT(p, t), steam_data.SH["h_by_P"][i][j], 1e-9)
        assert_close(steam.v_pT(p, t), steam_data.SH["v_by_P"][i][j], 1e-9)
        assert_close(steam.s_pT(p, t), steam_data.SH["s_by_P"][i][j], 1e-9)
        sh_checked += 1
    assert sh_checked > 0

    comp_checked = 0
    for i in sample_indices(len(steam_data.COMP["P"])):
        p = steam_data.COMP["P"][i]
        j = 0
        t = steam_data.COMP["T_by_P"][i][j]
        if steam.region_pT(p, t) != "compressed":
            continue
        assert_close(steam.u_pT(p, t), steam_data.COMP["u_by_P"][i][j], 1e-9)
        assert_close(steam.h_pT(p, t), steam_data.COMP["h_by_P"][i][j], 1e-9)
        assert_close(steam.v_pT(p, t), steam_data.COMP["v_by_P"][i][j], 1e-9)
        assert_close(steam.s_pT(p, t), steam_data.COMP["s_by_P"][i][j], 1e-9)
        comp_checked += 1
    assert comp_checked > 0


def test_mixture_identities_and_boundary_behavior():
    sat = steam.sat_T(100.0)
    x = 0.37
    assert_close(steam.x_from_h(steam.h_Tx(100.0, x), sat["hf"], sat["hg"]), x, 1e-10)
    assert_close(steam.x_from_u(steam.u_Tx(100.0, x), sat["uf"], sat["ug"]), x, 1e-10)
    assert_close(steam.x_from_v(steam.v_Tx(100.0, x), sat["vf"], sat["vg"]), x, 1e-10)
    assert_close(steam.x_from_s(steam.s_Tx(100.0, x), sat["sf"], sat["sg"]), x, 1e-10)

    p = 1000.0
    ts = steam.Tsat_p(p)
    sat_p = steam.sat_P(p)
    assert steam.region_pT(p, ts) == "two-phase"
    assert_close(steam.h_pT(p, ts), sat_p["hg"], 1e-9)
    assert_close(steam.u_pT(p, ts), sat_p["ug"], 1e-9)
    assert_close(steam.s_pT(p, ts), sat_p["sg"], 1e-9)
    assert_close(steam.v_pT(p, ts), sat_p["vg"], 1e-9)


def run_all():
    test_no_rows_dropped_and_block_lengths_match()
    test_random_spot_checks_match_csv_text()
    test_grid_node_exactness()
    test_mixture_identities_and_boundary_behavior()


if __name__ == "__main__":
    run_all()
    print("function matrix tests passed")
