"""Formal linear-interpolation verification tests for XSteam-Lite."""

import os
import random
import sys


ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tinspire import steam  # noqa: E402


def assert_close(actual, expected, tol):
    assert abs(actual - expected) <= tol, "actual={} expected={} tol={}".format(actual, expected, tol)


def manual_lerp(x, x0, x1, y0, y1):
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def manual_interp1(xs, ys, x):
    if len(xs) != len(ys):
        raise ValueError("xs and ys length mismatch")
    if len(xs) == 0:
        raise ValueError("empty grid")
    if len(xs) == 1:
        return ys[0]

    if x <= xs[0]:
        i0, i1 = 0, 1
    elif x >= xs[-1]:
        i0, i1 = len(xs) - 2, len(xs) - 1
    else:
        i0 = 0
        i1 = 1
        for idx in range(len(xs) - 1):
            if xs[idx] <= x <= xs[idx + 1]:
                i0 = idx
                i1 = idx + 1
                break
    return manual_lerp(x, xs[i0], xs[i1], ys[i0], ys[i1])


def test_interp1_midpoint_linearity():
    rng = random.Random(20260217)
    for _ in range(200):
        x0 = rng.uniform(-500.0, 500.0)
        x1 = x0 + rng.uniform(0.01, 500.0)
        y0 = rng.uniform(-1.0e4, 1.0e4)
        y1 = rng.uniform(-1.0e4, 1.0e4)

        xm = 0.5 * (x0 + x1)
        got = steam.interp1([x0, x1], [y0, y1], xm)
        expected = 0.5 * (y0 + y1)
        assert_close(got, expected, 1e-9)


def test_piecewise_region_recovers_linear_plane():
    # Synthetic linear field: f(P, T) = a*P + b*T + c
    a = 0.0375
    b = -1.625
    c = 42.0

    pgrid = [100.0, 300.0, 700.0]
    tgrid = [50.0, 150.0, 250.0, 350.0]

    region = {"P": list(pgrid), "T_by_P": [], "u_by_P": []}
    for p in pgrid:
        region["T_by_P"].append(list(tgrid))
        row = []
        for t in tgrid:
            row.append(a * p + b * t + c)
        region["u_by_P"].append(row)

    rng = random.Random(1401)
    for _ in range(200):
        p = rng.uniform(pgrid[0], pgrid[-1])
        t = rng.uniform(tgrid[0], tgrid[-1])
        got = steam._interp_piecewise_region(region, "u", p, t)
        expected = a * p + b * t + c
        assert_close(got, expected, 1e-10)


def test_blockwise_superheated_manual_linear_equivalence():
    sh = steam.SH
    overlaps = []
    for i in range(len(sh["P"]) - 1):
        t0 = sh["T_by_P"][i]
        t1 = sh["T_by_P"][i + 1]
        lo = max(min(t0), min(t1))
        hi = min(max(t0), max(t1))
        if hi > lo:
            overlaps.append((i, lo, hi))

    assert overlaps, "no overlapping SH pressure blocks found"

    rng = random.Random(90210)
    for _ in range(100):
        i, lo, hi = overlaps[rng.randrange(len(overlaps))]
        p0 = sh["P"][i]
        p1 = sh["P"][i + 1]
        p = rng.uniform(p0, p1)
        t = rng.uniform(lo, hi)

        for prop in ("u", "h", "s", "v"):
            engine = steam._interp_piecewise_region(sh, prop, p, t)

            vals0 = sh[prop + "_by_P"][i]
            vals1 = sh[prop + "_by_P"][i + 1]
            t0 = sh["T_by_P"][i]
            t1 = sh["T_by_P"][i + 1]

            prop0 = manual_interp1(t0, vals0, t)
            prop1 = manual_interp1(t1, vals1, t)
            manual = manual_lerp(p, p0, p1, prop0, prop1)
            assert_close(engine, manual, 1e-10)


def test_no_higher_order_interpolation_terms_in_steam_source():
    steam_path = os.path.join(ROOT, "tinspire", "steam.py")
    with open(steam_path, "r", encoding="utf-8") as handle:
        src = handle.read()
    lower = src.lower()

    forbidden_tokens = [
        "**2",
        "**3",
        "pow(",
        "spline",
        "cubic",
        "polynomial",
        "regression",
        "interp2d",
        "curve",
    ]
    for token in forbidden_tokens:
        assert token not in lower, "found forbidden token in steam.py: {}".format(token)

    assert "p_kpa * t_c" not in lower
    assert "t_c * p_kpa" not in lower


def run_all():
    test_interp1_midpoint_linearity()
    test_piecewise_region_recovers_linear_plane()
    test_blockwise_superheated_manual_linear_equivalence()
    test_no_higher_order_interpolation_terms_in_steam_source()


if __name__ == "__main__":
    run_all()
    print("linearity tests passed")
