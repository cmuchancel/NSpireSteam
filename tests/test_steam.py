"""Basic validation tests for XSteam-Lite core behavior."""

import io
import os
import sys
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import steam_data  # noqa: E402
from tinspire import steam  # noqa: E402


def assert_close(actual, expected, tol):
    assert abs(actual - expected) <= tol, "actual={} expected={} tol={}".format(actual, expected, tol)


def capture_output(fn, *args, **kwargs):
    buf = io.StringIO()
    with redirect_stdout(buf):
        ret = fn(*args, **kwargs)
    return ret, buf.getvalue()


def test_mixture_identities():
    sat = steam.sat_T(100.0)
    x = 0.2

    h_expected = sat["hf"] + x * (sat["hg"] - sat["hf"])
    u_expected = sat["uf"] + x * (sat["ug"] - sat["uf"])
    s_expected = sat["sf"] + x * (sat["sg"] - sat["sf"])
    v_expected = sat["vf"] + x * (sat["vg"] - sat["vf"])

    assert_close(steam.h_Tx(100.0, x), h_expected, 1e-12)
    assert_close(steam.u_Tx(100.0, x), u_expected, 1e-12)
    assert_close(steam.s_Tx(100.0, x), s_expected, 1e-12)
    assert_close(steam.v_Tx(100.0, x), v_expected, 1e-12)


def test_piecewise_node_exactness_comp_and_sh():
    # COMP node
    i = min(3, len(steam_data.COMP["P"]) - 1)
    j = min(3, len(steam_data.COMP["T_by_P"][i]) - 1)
    p = steam_data.COMP["P"][i]
    t = steam_data.COMP["T_by_P"][i][j]
    assert steam.region_pT(p, t) in ("compressed", "two-phase")
    if steam.region_pT(p, t) == "compressed":
        assert_close(steam.h_pT(p, t), steam_data.COMP["h_by_P"][i][j], 1e-12)
        assert_close(steam.u_pT(p, t), steam_data.COMP["u_by_P"][i][j], 1e-12)
        assert_close(steam.v_pT(p, t), steam_data.COMP["v_by_P"][i][j], 1e-12)
        assert_close(steam.s_pT(p, t), steam_data.COMP["s_by_P"][i][j], 1e-12)

    # SH node
    i = min(5, len(steam_data.SH["P"]) - 1)
    j = max(0, len(steam_data.SH["T_by_P"][i]) - 2)
    p = steam_data.SH["P"][i]
    t = steam_data.SH["T_by_P"][i][j]
    assert steam.region_pT(p, t) in ("superheated", "two-phase")
    if steam.region_pT(p, t) == "superheated":
        assert_close(steam.h_pT(p, t), steam_data.SH["h_by_P"][i][j], 1e-12)
        assert_close(steam.u_pT(p, t), steam_data.SH["u_by_P"][i][j], 1e-12)
        assert_close(steam.v_pT(p, t), steam_data.SH["v_by_P"][i][j], 1e-12)
        assert_close(steam.s_pT(p, t), steam_data.SH["s_by_P"][i][j], 1e-12)


def test_region_logic_at_saturation_boundary():
    p = steam_data.SAT_P["P"][min(20, len(steam_data.SAT_P["P"]) - 1)]
    ts = steam.Tsat_p(p)
    sat = steam.sat_P(p)

    assert steam.region_pT(p, ts) == "two-phase"
    assert steam.region_pT(p, ts - 5.0) == "compressed"
    assert steam.region_pT(p, ts + 5.0) == "superheated"

    # Boundary behavior returns saturated vapor values.
    assert_close(steam.h_pT(p, ts), sat["hg"], 1e-9)
    assert_close(steam.u_pT(p, ts), sat["ug"], 1e-9)
    assert_close(steam.v_pT(p, ts), sat["vg"], 1e-9)
    assert_close(steam.s_pT(p, ts), sat["sg"], 1e-9)


def test_lookup_sat_and_energy():
    sat_hits = steam.lookup("sat")
    sat_blob = "\n".join(sat_hits)
    assert "sat_T(T_C)" in sat_blob
    assert "sat_P(P_kPa)" in sat_blob
    assert "pSat_T(T_C)" in sat_blob
    assert "Tsat_p(P_kPa)" in sat_blob
    assert "[kPa]" in sat_blob
    assert "[°C]" in sat_blob

    energy_hits = steam.lookup("energy")
    energy_blob = "\n".join(energy_hits)
    assert "u_pT(P_kPa, T_C)" in energy_blob
    assert "h_pT(P_kPa, T_C)" in energy_blob
    assert "u_Tx(T_C, x)" in energy_blob
    assert "h_Tx(T_C, x)" in energy_blob
    assert "[kJ/kg]" in energy_blob

    state_hits = steam.lookup("state")
    state_blob = "\n".join(state_hits)
    assert "state(**known)" in state_blob
    assert "P_kPa [kPa]" in state_blob


def test_help_fn_and_units_wrappers():
    text = steam.help_fn("u_pT")
    assert "Requires: P_kPa [kPa], T_C [°C]" in text
    assert "Returns: u [kJ/kg]" in text

    p = steam_data.SH["P"][0]
    t = steam_data.SH["T_by_P"][0][-1]
    u_text = steam.u_pT_u(p, t)
    assert isinstance(u_text, str)
    assert u_text.endswith("kJ/kg")

    p_sat_text = steam.pSat_T_u(100.0)
    assert isinstance(p_sat_text, str)
    assert p_sat_text.endswith("kPa")


def test_with_units_sat_dict_rendering():
    rendered = steam.with_units("sat_T", 100.0)
    assert isinstance(rendered, str)
    assert "P_kPa:" in rendered and "kPa" in rendered
    assert "T_C:" in rendered and "°C" in rendered
    assert "vf:" in rendered and "m^3/kg" in rendered
    assert "uf:" in rendered and "kJ/kg" in rendered
    assert "sf:" in rendered and "kJ/kg-K" in rendered


def test_state_solver_paths():
    base = steam.state()
    for key in ("known", "region", "computed", "needs", "units", "notes"):
        assert key in base
    assert base["region"] == "unknown"

    # Superheated from (P, T)
    out = steam.state(P_kPa=1000, T_C=400)
    assert out["region"] == "superheated"
    assert "v" in out["computed"]
    assert "u" in out["computed"]
    assert "h" in out["computed"]
    assert "s" in out["computed"]

    # Compressed from (P, T)
    out = steam.state(P_kPa=20000, T_C=100)
    assert out["region"] == "compressed"
    assert "v" in out["computed"]
    assert "u" in out["computed"]
    assert "h" in out["computed"]
    assert "s" in out["computed"]

    # Two-phase boundary ambiguity from (P, T)
    out = steam.state(P_kPa=101.325, T_C=100)
    assert out["region"] == "two-phase"
    assert any("x" in item for item in out["needs"])

    # (T, x) saturated mixture
    out = steam.state(T_C=100, x=0.2)
    assert out["region"] == "two-phase"
    assert_close(out["computed"]["P_kPa"], steam.pSat_T(100), 0.5)
    assert "v" in out["computed"]
    assert "u" in out["computed"]
    assert "h" in out["computed"]
    assert "s" in out["computed"]

    # (P, v) saturated-mixture solve
    out = steam.state(P_kPa=100, v=0.004)
    assert out["region"] == "two-phase"
    assert 0.0 <= out["computed"]["x"] <= 1.0
    assert "u" in out["computed"]
    assert "h" in out["computed"]
    assert "s" in out["computed"]
    assert out["units"]["P_kPa"] == "kPa"
    assert out["units"]["T_C"] == "°C"


def test_state_help_text():
    ret, printed = capture_output(steam.state_help)
    assert ret is None
    assert "P_kPa [kPa]" in printed
    assert "T_C [°C]" in printed
    assert "Inside vapor dome" in printed
    assert printed.count("state(") >= 3
    assert "state_u(" in printed

    ret2, printed2 = capture_output(steam.state_u, P_kPa=1000, T_C=400)
    assert ret2 is None
    assert "state() result" in printed2
    assert "kPa" in printed2
    assert "°C" in printed2
    assert "kJ/kg" in printed2
    assert "kJ/kg-K" in printed2
    assert "m^3/kg" in printed2
    assert "-" in printed2
    assert any(ch.isdigit() for ch in printed2)

    ret3, printed3 = capture_output(steam.lookup, "state")
    assert isinstance(ret3, list)
    assert "state(**known)" in "\n".join(ret3)
    assert "state_help()" in printed3

    ret4, printed4 = capture_output(steam.help_fn, "state_help")
    assert isinstance(ret4, str)
    assert "P_kPa [kPa]" in printed4
    assert "state_u(" in printed4


def run_all():
    test_mixture_identities()
    test_piecewise_node_exactness_comp_and_sh()
    test_region_logic_at_saturation_boundary()
    test_lookup_sat_and_energy()
    test_help_fn_and_units_wrappers()
    test_with_units_sat_dict_rendering()
    test_state_solver_paths()
    test_state_help_text()


if __name__ == "__main__":
    run_all()
    print("all tests passed")
