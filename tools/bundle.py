#!/usr/bin/env python3
"""Build single-file TI-Nspire deploy bundle.

Concatenates:
1) data/steam_data.py
2) tinspire/steam.py

The data import in tinspire/steam.py is stripped so the output is a standalone
`tinspire/steam_bundle.py` module with no external dependencies.
"""

import argparse
import os


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def sanitize_steam_source(src):
    """Remove external-data import lines for single-file deployment."""
    kept = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("from data.steam_data import"):
            continue
        if stripped.startswith("import data.steam_data"):
            continue
        kept.append(line)
    return "\n".join(kept).strip() + "\n"


def build_bundle(data_path, steam_path, output_path):
    data_src = read_text(data_path).strip() + "\n\n"
    steam_src = sanitize_steam_source(read_text(steam_path))

    out = []
    out.append('"""XSteam-Lite TI-Nspire bundle (auto-generated)."""\n\n')
    out.append("# ---- embedded data tables ----\n")
    out.append(data_src)
    out.append("# ---- embedded steam core ----\n")
    out.append(steam_src)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("".join(out))


def main():
    parser = argparse.ArgumentParser(description="Build single-file TI deploy bundle")
    parser.add_argument("--data", default="data/steam_data.py", help="Path to steam_data.py")
    parser.add_argument("--steam", default="tinspire/steam.py", help="Path to core steam module")
    parser.add_argument("--output", default="tinspire/steam_bundle.py", help="Output bundle path")
    args = parser.parse_args()

    build_bundle(args.data, args.steam, args.output)
if __name__ == "__main__":
    main()
