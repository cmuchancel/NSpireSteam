# XSteam-Lite

[![Python Compatible](https://img.shields.io/badge/Python-3.x-blue)](#)
[![TI-Nspire Compatible](https://img.shields.io/badge/TI--Nspire-CX%20II%20CAS-green)](#)
[![Interpolation](https://img.shields.io/badge/Model-Linear%20Only-black)](#)

XSteam-Lite is a deterministic, table-driven steam property engine designed for constrained environments, with canonical CSV preservation, piecewise linear interpolation, and a standalone TI-Nspire deployment bundle.

## 🚀 What This Is

XSteam-Lite is a production-oriented steam table engine that reads immutable canonical CSV tables, builds embedded runtime arrays, and computes properties using strict linear interpolation only. It supports non-rectangular superheated/compressed tables, a flexible state solver, and single-file TI-Nspire deployment.

## ✨ Key Features

- Canonical immutable table data in `data/canonical_csv/`
- Strict linear interpolation (`lerp` + piecewise 1D/2D composition)
- Piecewise support for non-rectangular superheated/compressed tables
- Full state solver via `state(**known)`
- Units-aware auto-print via `state_u()` and `_u` helpers
- Built-in command discovery via `lookup()` and `help_fn()`
- Standalone TI bundle via `tinspire/steam_bundle.py`

## 🧠 Architecture

Build and runtime flow:

1. `data/canonical_csv/Table_A1.csv` .. `Table_A4.csv`
2. `tools/build_data.py` + `data/schema.json`
3. `data/steam_data.py` (embedded arrays)
4. `tinspire/steam.py` (runtime engine)
5. `tools/bundle.py` -> `tinspire/steam_bundle.py` (standalone deployable)

Why piecewise interpolation:

- A3/A4 tables are non-rectangular across pressure blocks.
- Piecewise interpolation preserves full table coverage without fabricating values.

Why no rounding in computation:

- Numeric computations stay in raw float space to preserve table fidelity.
- Formatting is separated from computation.

Why no IF97 equations:

- This project is intentionally table-faithful and inspectable.
- It prioritizes deterministic behavior and deployment simplicity on TI hardware.

## 📐 Numerical Model

- Linear interpolation only.
- No spline interpolation.
- No polynomial fitting.
- Deterministic region logic via `region_pT(P_kPa, T_C)` with saturation tolerance.
- Saturation boundary pT behavior returns saturated vapor boundary values.

## 🔍 State Solver

Primary APIs:

- `state(**known)` -> structured solver result dict
- `state_u(**known)` -> auto-prints formatted solver output
- `state_help()` -> auto-prints solver usage guide

Examples:

```python
from tinspire import steam

steam.state(P_kPa=1000, T_C=400)
steam.state(P_kPa=100, v=0.004)
steam.state_u(T_C=100, x=0.2)
```

Vapor dome behavior:

- Inside two-phase conditions, `state()` will not guess `x`.
- If insufficient independent properties are provided, `needs` is returned.

## 🖥 TI Usage

```python
# 1) Build bundle on desktop:
# python tools/build_data.py
# python tools/bundle.py
#
# 2) Copy tinspire/steam_bundle.py into TI Python environment.

import steam_bundle as steam

steam.state_help()
steam.state_u(P_kPa=1000, T_C=400)
steam.lookup("sat")
```

## 🧪 Testing & Verification

Tests cover:

- mixture identity and consistency checks
- grid-node exactness for A3/A4 interpolation
- linearity verification (1D + piecewise plane behavior)
- saturation boundary and region classification behavior
- data/bundle integrity and standalone purity constraints

Run:

```bash
python tools/build_data.py
python tools/bundle.py
python tests/test_steam.py
python tests/test_function_matrix.py
python tests/test_data_integrity.py
python tests/test_linearity.py
```

## 📁 Repository Structure

```text
.
├── README.md
├── .gitignore
├── data
│   ├── canonical_csv
│   │   ├── Table_A1.csv
│   │   ├── Table_A2.csv
│   │   ├── Table_A3.csv
│   │   └── Table_A4.csv
│   ├── schema.json
│   ├── steam_data.py
│   └── build_report.txt
├── tinspire
│   ├── steam.py
│   └── steam_bundle.py
├── tools
│   ├── build_data.py
│   └── bundle.py
└── tests
    ├── test_steam.py
    ├── test_function_matrix.py
    ├── test_data_integrity.py
    └── test_linearity.py
```

## 🎯 Design Philosophy

- Deterministic
- Inspectable
- Table-faithful
- Minimal
- No hidden magic

## Changelog

- `1.0.0`
  - Stabilize canonical CSV workflow and deterministic schema-driven build.
  - Finalize linear-only interpolation runtime and state solver APIs.
  - Deliver standalone TI bundle and repository hardening checks.
