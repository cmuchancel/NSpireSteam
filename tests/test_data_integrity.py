"""Data integrity checks for immutable canonical CSV workflow."""

import os
import subprocess
import sys
import importlib
import re


ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CANONICAL = [
    "data/canonical_csv/Table_A1.csv",
    "data/canonical_csv/Table_A2.csv",
    "data/canonical_csv/Table_A3.csv",
    "data/canonical_csv/Table_A4.csv",
]
LEGACY_SHOULD_NOT_EXIST = [
    "README 2.md",
    "tests/test_data_integrity 2.py",
    "tests/test_steam 2.py",
    "tinspire/steam 2.py",
    "tinspire/steam 3.py",
    "tools/build_data 2.py",
    "tools/build_data 3.py",
    "data/linear_interpolation_verification.txt",
]


def abs_path(rel):
    return os.path.join(ROOT, rel)


def test_canonical_csv_files_exist():
    missing = []
    for rel in CANONICAL:
        if not os.path.exists(abs_path(rel)):
            missing.append(rel)
    assert not missing, "missing canonical CSV files: {}".format(", ".join(missing))


def test_schema_and_build_outputs():
    assert os.path.exists(abs_path("data/schema.json")), "missing data/schema.json"

    subprocess.run([sys.executable, "tools/build_data.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "tools/bundle.py"], cwd=ROOT, check=True)

    assert os.path.exists(abs_path("data/steam_data.py")), "missing data/steam_data.py"
    assert os.path.exists(abs_path("data/build_report.txt")), "missing data/build_report.txt"
    assert os.path.exists(abs_path("tinspire/steam_bundle.py")), "missing tinspire/steam_bundle.py"

    subprocess.run([sys.executable, "-m", "py_compile", "tinspire/steam_bundle.py"], cwd=ROOT, check=True)

    steam_data = importlib.import_module("data.steam_data")
    assert hasattr(steam_data, "PRECISION"), "data.steam_data missing PRECISION metadata"
    precision = getattr(steam_data, "PRECISION")
    assert isinstance(precision, dict), "PRECISION must be a dict"
    for key in ("P_kPa", "T_C", "v", "u", "h", "s", "x"):
        assert key in precision, "PRECISION missing key {}".format(key)


def test_no_rounding_or_fixed_decimal_format_in_core_files():
    targets = ["tinspire/steam.py", "tools/build_data.py"]
    fixed_f_pattern = re.compile(r":\.\d+f")
    disallowed_g_pattern = re.compile(r":\.(?!15g)\d+g")

    for rel in targets:
        src = open(abs_path(rel), "r", encoding="utf-8").read()
        assert "round(" not in src, "round() found in {}".format(rel)
        assert not fixed_f_pattern.search(src), "fixed-decimal float format found in {}".format(rel)
        assert not disallowed_g_pattern.search(src), "unexpected precision g-format found in {}".format(rel)


def test_no_legacy_artifacts():
    leftovers = [rel for rel in LEGACY_SHOULD_NOT_EXIST if os.path.exists(abs_path(rel))]
    assert not leftovers, "legacy artifacts still present: {}".format(", ".join(leftovers))


def test_bundle_standalone_purity():
    bundle_src = open(abs_path("tinspire/steam_bundle.py"), "r", encoding="utf-8").read()
    for line in bundle_src.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("from "), "bundle contains from-import: {}".format(stripped)
        assert not stripped.startswith("import "), "bundle contains import: {}".format(stripped)
    assert "open(" not in bundle_src, "bundle must not perform filesystem reads"
    for marker in ("canonical_csv", "schema.json", "data/schema.json", "csv.", "json."):
        assert marker not in bundle_src, "bundle contains forbidden runtime marker {}".format(marker)


def run_all():
    test_canonical_csv_files_exist()
    test_schema_and_build_outputs()
    test_no_rounding_or_fixed_decimal_format_in_core_files()
    test_no_legacy_artifacts()
    test_bundle_standalone_purity()


if __name__ == "__main__":
    run_all()
    print("data integrity tests passed")
