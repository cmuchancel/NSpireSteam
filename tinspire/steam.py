"""XSteam-Lite core property functions for TI-Nspire-compatible Python.

This module uses table lookup + interpolation only (no IF97 equations).
All pressure inputs are in kPa and all temperatures are in degC.
"""

from data.steam_data import COMP, SAT_P, SAT_T, SH


SAT_TOL_C = 0.25
_SAT_P_FALLBACK = None
__version__ = "1.0.0"


def bracket(xs, x):
    """Return index pair (i0, i1) such that xs[i0] <= x <= xs[i1]."""
    n = len(xs)
    if n < 2:
        raise ValueError("bracket requires at least two grid points")

    if x <= xs[0]:
        return 0, 1
    if x >= xs[-1]:
        return n - 2, n - 1

    lo = 0
    hi = n - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    return lo, hi


def lerp(x, x0, x1, y0, y1):
    """Linear interpolation y(x) between points (x0, y0) and (x1, y1)."""
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def interp1(xs, ys, x):
    """1D table lookup with linear interpolation."""
    if len(xs) != len(ys):
        raise ValueError("xs and ys length mismatch")
    if len(xs) == 0:
        raise ValueError("interp1 requires at least one grid point")
    if len(xs) == 1:
        return ys[0]
    i0, i1 = bracket(xs, x)
    return lerp(x, xs[i0], xs[i1], ys[i0], ys[i1])


def _build_sat_p_fallback():
    idx = list(range(len(SAT_T["P"])))
    idx.sort(key=lambda i: SAT_T["P"][i])
    out = {}
    for key in ("T", "P", "vf", "vg", "uf", "ug", "hf", "hg", "sf", "sg"):
        out[key] = [SAT_T[key][i] for i in idx]
    return out


def _sat_p_table():
    global _SAT_P_FALLBACK

    if isinstance(SAT_P, dict) and "P" in SAT_P and "T" in SAT_P and len(SAT_P["P"]) >= 2:
        return SAT_P

    if _SAT_P_FALLBACK is None:
        _SAT_P_FALLBACK = _build_sat_p_fallback()
    return _SAT_P_FALLBACK


def sat_T(T_C):
    """Return saturated properties at temperature T_C (degC)."""
    out = {"T": T_C, "P": interp1(SAT_T["T"], SAT_T["P"], T_C)}
    for key in ("vf", "vg", "uf", "ug", "hf", "hg", "sf", "sg"):
        out[key] = interp1(SAT_T["T"], SAT_T[key], T_C)
    return out


def sat_P(P_kPa):
    """Return saturated properties at pressure P_kPa."""
    table = _sat_p_table()
    out = {"P": P_kPa, "T": interp1(table["P"], table["T"], P_kPa)}
    for key in ("vf", "vg", "uf", "ug", "hf", "hg", "sf", "sg"):
        out[key] = interp1(table["P"], table[key], P_kPa)
    return out


def pSat_T(T_C):
    """Saturation pressure in kPa as a function of temperature in degC."""
    return interp1(SAT_T["T"], SAT_T["P"], T_C)


def Tsat_p(P_kPa):
    """Saturation temperature in degC as a function of pressure in kPa."""
    table = _sat_p_table()
    return interp1(table["P"], table["T"], P_kPa)


def mix(prop_f, prop_g, x):
    """Quality blend of saturated liquid/vapor properties."""
    if x < 0.0 or x > 1.0:
        raise ValueError("quality x must be within [0, 1]")
    return prop_f + x * (prop_g - prop_f)


def _x_from_prop(value, prop_f, prop_g):
    if prop_g == prop_f:
        raise ValueError("cannot compute quality for equal f/g properties")
    return (value - prop_f) / (prop_g - prop_f)


def x_from_v(v, vf, vg):
    return _x_from_prop(v, vf, vg)


def x_from_u(u, uf, ug):
    return _x_from_prop(u, uf, ug)


def x_from_h(h, hf, hg):
    return _x_from_prop(h, hf, hg)


def x_from_s(s, sf, sg):
    return _x_from_prop(s, sf, sg)


def u_Tx(T_C, x):
    sat = sat_T(T_C)
    return mix(sat["uf"], sat["ug"], x)


def h_Tx(T_C, x):
    sat = sat_T(T_C)
    return mix(sat["hf"], sat["hg"], x)


def s_Tx(T_C, x):
    sat = sat_T(T_C)
    return mix(sat["sf"], sat["sg"], x)


def v_Tx(T_C, x):
    sat = sat_T(T_C)
    return mix(sat["vf"], sat["vg"], x)


def region_pT(P_kPa, T_C):
    """Return region for (P, T): compressed, two-phase, or superheated."""
    ts = Tsat_p(P_kPa)
    if abs(T_C - ts) <= SAT_TOL_C:
        return "two-phase"
    if T_C < ts:
        return "compressed"
    return "superheated"


def _interp_piecewise_region(region, prop, P_kPa, T_C):
    pgrid = region["P"]
    t_key = "T_by_P"
    prop_key = prop + "_by_P"

    if len(pgrid) == 0:
        raise ValueError("empty region table")
    if len(pgrid) == 1:
        return interp1(region[t_key][0], region[prop_key][0], T_C)

    i0, i1 = bracket(pgrid, P_kPa)
    p0 = pgrid[i0]
    p1 = pgrid[i1]

    prop0 = interp1(region[t_key][i0], region[prop_key][i0], T_C)
    prop1 = interp1(region[t_key][i1], region[prop_key][i1], T_C)
    return lerp(P_kPa, p0, p1, prop0, prop1)


def _sat_boundary_prop(prop, P_kPa):
    sat = sat_P(P_kPa)
    if prop == "u":
        return sat["ug"]
    if prop == "h":
        return sat["hg"]
    if prop == "s":
        return sat["sg"]
    if prop == "v":
        return sat["vg"]
    raise ValueError("unknown property: " + str(prop))


def _prop_pT_kPa(prop, P_kPa, T_C):
    reg = region_pT(P_kPa, T_C)
    if reg == "superheated":
        return _interp_piecewise_region(SH, prop, P_kPa, T_C)
    if reg == "compressed":
        return _interp_piecewise_region(COMP, prop, P_kPa, T_C)
    return _sat_boundary_prop(prop, P_kPa)


def u_pT(P_kPa, T_C):
    """u (kJ/kg) from pressure (kPa) and temperature (degC)."""
    return _prop_pT_kPa("u", P_kPa, T_C)


def h_pT(P_kPa, T_C):
    """h (kJ/kg) from pressure (kPa) and temperature (degC)."""
    return _prop_pT_kPa("h", P_kPa, T_C)


def s_pT(P_kPa, T_C):
    """s (kJ/kg-K) from pressure (kPa) and temperature (degC)."""
    return _prop_pT_kPa("s", P_kPa, T_C)


def v_pT(P_kPa, T_C):
    """v (m^3/kg) from pressure (kPa) and temperature (degC)."""
    return _prop_pT_kPa("v", P_kPa, T_C)


_STATE_UNITS = {
    "P": "kPa",
    "T": "°C",
    "P_kPa": "kPa",
    "T_C": "°C",
    "Tsat_C": "°C",
    "v": "m^3/kg",
    "u": "kJ/kg",
    "h": "kJ/kg",
    "s": "kJ/kg-K",
    "x": "-",
    "vf": "m^3/kg",
    "vg": "m^3/kg",
    "uf": "kJ/kg",
    "ug": "kJ/kg",
    "hf": "kJ/kg",
    "hg": "kJ/kg",
    "sf": "kJ/kg-K",
    "sg": "kJ/kg-K",
    "sat_vf": "m^3/kg",
    "sat_vg": "m^3/kg",
    "sat_uf": "kJ/kg",
    "sat_ug": "kJ/kg",
    "sat_hf": "kJ/kg",
    "sat_hg": "kJ/kg",
    "sat_sf": "kJ/kg-K",
    "sat_sg": "kJ/kg-K",
}


def _state_template(known_clean):
    return {
        "known": dict(known_clean),
        "region": "unknown",
        "computed": {},
        "sat": {},
        "needs": [],
        "units": dict(_STATE_UNITS),
        "notes": [],
    }


def _state_default_needs():
    return [
        "P_kPa and T_C",
        "P_kPa and x",
        "T_C and x",
        "P_kPa and one of v/u/h/s",
        "T_C and one of v/u/h/s",
    ]


def _first_known_prop(known_clean):
    for key in ("v", "u", "h", "s"):
        if key in known_clean:
            return key, known_clean[key]
    return None, None


def _x_from_named_prop(prop_name, value, sat):
    if prop_name == "v":
        return x_from_v(value, sat["vf"], sat["vg"])
    if prop_name == "u":
        return x_from_u(value, sat["uf"], sat["ug"])
    if prop_name == "h":
        return x_from_h(value, sat["hf"], sat["hg"])
    if prop_name == "s":
        return x_from_s(value, sat["sf"], sat["sg"])
    raise ValueError("unsupported property for quality solve: " + str(prop_name))


def _mix_from_sat(sat, x):
    return {
        "x": x,
        "v": mix(sat["vf"], sat["vg"], x),
        "u": mix(sat["uf"], sat["ug"], x),
        "h": mix(sat["hf"], sat["hg"], x),
        "s": mix(sat["sf"], sat["sg"], x),
    }


def _state_add_two_phase_sat_context(result, sat):
    result["computed"]["sat_vf"] = sat["vf"]
    result["computed"]["sat_vg"] = sat["vg"]
    result["computed"]["sat_uf"] = sat["uf"]
    result["computed"]["sat_ug"] = sat["ug"]
    result["computed"]["sat_hf"] = sat["hf"]
    result["computed"]["sat_hg"] = sat["hg"]
    result["computed"]["sat_sf"] = sat["sf"]
    result["computed"]["sat_sg"] = sat["sg"]


def _state_apply_quality(result, sat, x):
    if x < 0.0 or x > 1.0:
        result["region"] = "unknown"
        result["computed"]["x"] = x
        result["notes"].append("x must be within [0, 1] for saturated mixture.")
        return False
    result["computed"].update(_mix_from_sat(sat, x))
    result["region"] = "two-phase"
    return True


def state(**known):
    """Flexible state solver from partial known properties.

    Accepted keys:
    - P_kPa, T_C, x, v, u, h, s

    Returns dict:
    - known, region, computed, needs, units, notes
    """
    accepted = ("P_kPa", "T_C", "x", "v", "u", "h", "s")
    known_clean = {}
    notes = []

    for key, value in known.items():
        if key not in accepted:
            notes.append("Ignoring unsupported key: " + str(key))
            continue
        try:
            known_clean[key] = float(value)
        except Exception:
            notes.append("Ignoring non-numeric value for " + str(key))

    result = _state_template(known_clean)
    result["notes"].extend(notes)

    P_kPa = known_clean.get("P_kPa")
    T_C = known_clean.get("T_C")
    x = known_clean.get("x")
    p_name, p_value = _first_known_prop(known_clean)

    # A) Known P_kPa and T_C
    if P_kPa is not None and T_C is not None:
        try:
            reg = region_pT(P_kPa, T_C)
            result["region"] = reg
            if reg == "compressed" or reg == "superheated":
                result["computed"]["v"] = v_pT(P_kPa, T_C)
                result["computed"]["u"] = u_pT(P_kPa, T_C)
                result["computed"]["h"] = h_pT(P_kPa, T_C)
                result["computed"]["s"] = s_pT(P_kPa, T_C)
                return result

            # two-phase boundary
            sat = sat_P(P_kPa)
            result["sat"] = dict(sat)
            result["computed"]["Tsat_C"] = sat["T"]
            _state_add_two_phase_sat_context(result, sat)

            # Use provided quality/property if available, but never guess.
            if x is not None:
                _state_apply_quality(result, sat, x)
                return result
            if p_name is not None:
                x_guess = _x_from_named_prop(p_name, p_value, sat)
                if x_guess < 0.0 or x_guess > 1.0:
                    result["region"] = "unknown"
                    result["computed"]["x"] = x_guess
                    result["needs"] = ["T_C outside saturation boundary or a consistent two-phase property"]
                    result["notes"].append(
                        "Provided {} with P_kPa,T_C does not map to saturated mixture (x outside [0,1]).".format(
                            p_name
                        )
                    )
                    return result
                _state_apply_quality(result, sat, x_guess)
                return result

            result["needs"] = ["x or one of v/u/h/s"]
            result["notes"].append("At saturation boundary, one extra independent property is required.")
            return result
        except Exception as exc:
            result["region"] = "unknown"
            result["notes"].append("Could not solve from P_kPa,T_C: " + str(exc))
            result["needs"] = _state_default_needs()
            return result

    # B) Known T_C and x
    if T_C is not None and x is not None:
        try:
            sat = sat_T(T_C)
            result["sat"] = dict(sat)
            result["computed"]["P_kPa"] = sat["P"]
            if _state_apply_quality(result, sat, x):
                return result
            result["needs"] = ["x in [0, 1]"]
            return result
        except Exception as exc:
            result["region"] = "unknown"
            result["needs"] = _state_default_needs()
            result["notes"].append("Could not solve from T_C,x: " + str(exc))
            return result

    # C) Known P_kPa and x
    if P_kPa is not None and x is not None:
        try:
            sat = sat_P(P_kPa)
            result["sat"] = dict(sat)
            result["computed"]["T_C"] = sat["T"]
            if _state_apply_quality(result, sat, x):
                return result
            result["needs"] = ["x in [0, 1]"]
            return result
        except Exception as exc:
            result["region"] = "unknown"
            result["needs"] = _state_default_needs()
            result["notes"].append("Could not solve from P_kPa,x: " + str(exc))
            return result

    # D) Known P_kPa and one of v/u/h/s (no T_C)
    if P_kPa is not None and T_C is None and p_name is not None:
        try:
            sat = sat_P(P_kPa)
            result["sat"] = dict(sat)
            x_calc = _x_from_named_prop(p_name, p_value, sat)
            result["computed"]["T_C"] = sat["T"]
            result["computed"]["x"] = x_calc
            if x_calc < 0.0 or x_calc > 1.0:
                result["region"] = "unknown"
                result["needs"] = ["T_C"]
                result["notes"].append(
                    "Computed x is outside [0,1]; not a saturated mixture at this P_kPa. Provide T_C."
                )
                return result

            result["region"] = "two-phase"
            result["computed"].update(_mix_from_sat(sat, x_calc))
            return result
        except Exception as exc:
            result["region"] = "unknown"
            result["needs"] = _state_default_needs()
            result["notes"].append("Could not solve from P_kPa and {}: {}".format(p_name, exc))
            return result

    # E) Known T_C and one of v/u/h/s (no P_kPa)
    if T_C is not None and P_kPa is None and p_name is not None:
        try:
            sat = sat_T(T_C)
            result["sat"] = dict(sat)
            x_calc = _x_from_named_prop(p_name, p_value, sat)
            result["computed"]["P_kPa"] = sat["P"]
            result["computed"]["x"] = x_calc
            if x_calc < 0.0 or x_calc > 1.0:
                result["region"] = "unknown"
                result["needs"] = ["P_kPa or additional independent property (e.g. T_C with P_kPa)"]
                result["notes"].append(
                    "Computed x is outside [0,1]; not a saturated mixture at this T_C. Provide P_kPa."
                )
                return result

            result["region"] = "two-phase"
            result["computed"].update(_mix_from_sat(sat, x_calc))
            return result
        except Exception as exc:
            result["region"] = "unknown"
            result["needs"] = _state_default_needs()
            result["notes"].append("Could not solve from T_C and {}: {}".format(p_name, exc))
            return result

    # F) Incomplete/unsupported combination
    result["region"] = "unknown"
    result["needs"] = _state_default_needs()
    if not known_clean:
        result["notes"].append("No usable known properties were provided.")
    else:
        result["notes"].append("Insufficient independent properties to resolve state.")
    return result


def fmt(x):
    """Return high-precision text for TI display without manual rounding."""
    if x is None:
        return "None"
    if isinstance(x, (int, float)):
        return "{:.15g}".format(x)
    return str(x)


def fmt_with_unit(x, unit):
    """Format a value and append unit text."""
    if unit:
        return "{} {}".format(fmt(x), unit)
    return fmt(x)


def _unit_from_returns(returns_spec):
    start = returns_spec.find("[")
    end = returns_spec.find("]", start + 1)
    if start < 0 or end < 0:
        return ""
    unit = returns_spec[start + 1 : end].strip()
    if unit in ("str", "list[str]", "dict"):
        return ""
    return unit


def _format_sat_dict(values):
    prop_units = {
        "P": "kPa",
        "T": "°C",
        "vf": "m^3/kg",
        "vg": "m^3/kg",
        "uf": "kJ/kg",
        "ug": "kJ/kg",
        "hf": "kJ/kg",
        "hg": "kJ/kg",
        "sf": "kJ/kg-K",
        "sg": "kJ/kg-K",
        "v": "m^3/kg",
        "u": "kJ/kg",
        "h": "kJ/kg",
        "s": "kJ/kg-K",
        "x": "-",
    }
    order = ["P", "T", "vf", "vg", "uf", "ug", "hf", "hg", "sf", "sg", "x"]
    extra = []
    for key in values:
        if key not in order:
            extra.append(key)
    extra.sort()

    lines = []
    for key in order + extra:
        if key not in values:
            continue
        value = values[key]
        label = "P_kPa" if key == "P" else ("T_C" if key == "T" else key)
        if isinstance(value, (int, float)):
            unit = prop_units.get(key, "")
            if unit:
                lines.append("{}: {}".format(label, fmt_with_unit(value, unit)))
            else:
                lines.append("{}: {}".format(label, fmt(value)))
        else:
            lines.append("{}: {}".format(label, value))
    return "\n".join(lines)


def _state_section_keys(values):
    base = [
        "P_kPa",
        "T_C",
        "Tsat_C",
        "x",
        "v",
        "u",
        "h",
        "s",
        "vf",
        "vg",
        "uf",
        "ug",
        "hf",
        "hg",
        "sf",
        "sg",
        "sat_vf",
        "sat_vg",
        "sat_uf",
        "sat_ug",
        "sat_hf",
        "sat_hg",
        "sat_sf",
        "sat_sg",
        "P",
        "T",
    ]
    extra = []
    for key in values:
        if key not in base:
            extra.append(key)
    extra.sort()
    return base + extra


def _state_display_key(key):
    if key == "P":
        return "P_kPa"
    if key == "T":
        return "T_C"
    return key


def _state_unit_for_key(key, units_map):
    if key in units_map:
        return units_map[key]
    if key == "P":
        return units_map.get("P_kPa", "kPa")
    if key == "T":
        return units_map.get("T_C", "°C")
    return _STATE_UNITS.get(key, "")


def _format_state_section(values, units_map):
    lines = []
    for key in _state_section_keys(values):
        if key not in values:
            continue
        val = values[key]
        label = _state_display_key(key)
        if isinstance(val, (int, float)):
            unit = _state_unit_for_key(key, units_map)
            lines.append("  {}: {}".format(label, fmt_with_unit(val, unit)))
        else:
            lines.append("  {}: {}".format(label, fmt(val)))
    if not lines:
        lines.append("  (none)")
    return lines


def _format_state_result(result):
    units_map = dict(_STATE_UNITS)
    units_map.update(result.get("units", {}))

    lines = []
    lines.append("state() result")
    lines.append("region: {}".format(result.get("region", "unknown")))
    lines.append("known:")
    lines.extend(_format_state_section(result.get("known", {}), units_map))
    lines.append("computed:")
    lines.extend(_format_state_section(result.get("computed", {}), units_map))

    sat = result.get("sat", {})
    lines.append("sat:")
    lines.extend(_format_state_section(sat, units_map))

    needs = result.get("needs", [])
    lines.append("needs:")
    if needs:
        for item in needs:
            lines.append("  - {}".format(item))
    else:
        lines.append("  (none)")

    notes = result.get("notes", [])
    lines.append("notes:")
    if notes:
        for item in notes:
            lines.append("  - {}".format(item))
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def state_u(**known):
    """Solve state and print formatted output with units."""
    result = state(**known)
    text = _format_state_result(result)
    print(text)
    return None


def _state_help_text():
    lines = []
    lines.append("state() solves whatever it can from known properties.")
    lines.append("")
    lines.append("Accepted inputs:")
    lines.append("P_kPa [kPa], T_C [°C], x [-], v [m^3/kg], u [kJ/kg], h [kJ/kg], s [kJ/kg-K]")
    lines.append("")
    lines.append("Returns keys:")
    lines.append("region, computed, needs, sat, notes, units")
    lines.append("")
    lines.append("Region logic:")
    lines.append("compressed / superheated / two-phase")
    lines.append("")
    lines.append("Inside vapor dome:")
    lines.append("If x is not provided, state() will NOT guess x; it returns needs.")
    lines.append("")
    lines.append("Known combinations:")
    lines.append("state(P_kPa=..., T_C=...)")
    lines.append("state(P_kPa=..., x=...)")
    lines.append("state(T_C=..., x=...)")
    lines.append("state(P_kPa=..., v=...)")
    lines.append("state(T_C=..., h=...)")
    lines.append("")
    lines.append("Auto-print:")
    lines.append("state_u(P_kPa=1000, T_C=400)")
    lines.append("state_u(P_kPa=101.325, T_C=100)")
    lines.append("state_u(T_C=100, x=0.2)")
    return "\n".join(lines)


def state_help():
    """Print TI-friendly guide for state() and state_u()."""
    text = _state_help_text()
    print(text)
    return None


def with_units(func_name, *args):
    """Call a numeric function by name and return a formatted units string."""
    fn = globals().get(func_name)
    if not callable(fn):
        return "Function '{}' not found. Use lookup() to search commands.".format(func_name)

    result = fn(*args)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if "region" in result and "computed" in result and "needs" in result:
            return _format_state_result(result)
        return _format_sat_dict(result)
    if isinstance(result, (int, float)):
        meta = _DOCS.get(func_name, {})
        unit = _unit_from_returns(meta.get("returns", ""))
        return fmt_with_unit(result, unit)
    return str(result)


def u_pT_u(P_kPa, T_C):
    return fmt_with_unit(u_pT(P_kPa, T_C), "kJ/kg")


def h_pT_u(P_kPa, T_C):
    return fmt_with_unit(h_pT(P_kPa, T_C), "kJ/kg")


def s_pT_u(P_kPa, T_C):
    return fmt_with_unit(s_pT(P_kPa, T_C), "kJ/kg-K")


def v_pT_u(P_kPa, T_C):
    return fmt_with_unit(v_pT(P_kPa, T_C), "m^3/kg")


def pSat_T_u(T_C):
    return fmt_with_unit(pSat_T(T_C), "kPa")


def Tsat_p_u(P_kPa):
    return fmt_with_unit(Tsat_p(P_kPa), "°C")


def u_Tx_u(T_C, x):
    return fmt_with_unit(u_Tx(T_C, x), "kJ/kg")


def h_Tx_u(T_C, x):
    return fmt_with_unit(h_Tx(T_C, x), "kJ/kg")


def s_Tx_u(T_C, x):
    return fmt_with_unit(s_Tx(T_C, x), "kJ/kg-K")


def v_Tx_u(T_C, x):
    return fmt_with_unit(v_Tx(T_C, x), "m^3/kg")


def _lookup_score(keyword, name, meta):
    key = keyword.lower()
    lname = name.lower()
    tags = [str(x).lower() for x in meta.get("tags", [])]
    sig = str(meta.get("sig", "")).lower()
    does = str(meta.get("does", "")).lower()
    returns = str(meta.get("returns", "")).lower()
    requires = " ".join(meta.get("requires", [])).lower()

    if key == lname:
        return 0
    if key in tags:
        return 1
    if key in lname:
        return 2
    for tag in tags:
        if key in tag:
            return 3
    if key in sig:
        return 4
    if key in does:
        return 5
    if key in returns or key in requires:
        return 6
    return None


def _lookup_line(meta):
    requires = meta.get("requires", [])
    if requires:
        requires_text = ", ".join(requires)
    else:
        requires_text = "none"
    return "{} -> {} | {} Requires: {}".format(
        meta.get("sig", ""),
        meta.get("returns", ""),
        meta.get("does", ""),
        requires_text,
    )


def lookup(keyword):
    """Keyword search over available commands and units metadata."""
    key = str(keyword).strip().lower()
    if not key:
        key = "all"

    hits = []
    for name in _DOCS:
        meta = _DOCS[name]
        score = _lookup_score(key, name, meta)
        if key == "all":
            score = 99
        if score is None:
            continue
        hits.append((score, name.lower(), _lookup_line(meta)))
    hits.sort()
    out = [item[2] for item in hits]
    for line in out:
        print(line)
    return out


def help_fn(name):
    """Return a multi-line help block for one function."""
    query = str(name).strip().lower()
    if query == "state_help":
        text = _state_help_text()
        print(text)
        return text

    target = None
    for key in _DOCS:
        if key.lower() == query:
            target = key
            break

    if target is None:
        text = "Function '{}' not found. Use lookup('keyword') to search.".format(name)
        print(text)
        return text

    meta = _DOCS[target]
    lines = []
    lines.append("Signature: {}".format(meta.get("sig", "")))
    lines.append("Does: {}".format(meta.get("does", "")))
    lines.append("Requires: {}".format(", ".join(meta.get("requires", []))))
    lines.append("Returns: {}".format(meta.get("returns", "")))
    if "notes" in meta and meta["notes"]:
        lines.append("Notes: {}".format(meta["notes"]))
    if target == "state":
        lines.append("Notes: See state_help() for full solver guide and examples.")
    lines.append("Tags: {}".format(", ".join(meta.get("tags", []))))
    text = "\n".join(lines)
    print(text)
    return text


def list_commands():
    """List all known public command signatures in alphabetical order."""
    sigs = [meta.get("sig", "") for _, meta in sorted(_DOCS.items(), key=lambda x: x[0].lower())]
    return sorted(sigs)


_DOCS = {
    "Tsat_p": {
        "sig": "Tsat_p(P_kPa)",
        "does": "Saturation temperature from pressure.",
        "requires": ["P_kPa [kPa]"],
        "returns": "T_sat [°C]",
        "tags": ["sat", "saturation", "pressure", "temperature", "tsat"],
    },
    "Tsat_p_u": {
        "sig": "Tsat_p_u(P_kPa)",
        "does": "Formatted saturation temperature from pressure.",
        "requires": ["P_kPa [kPa]"],
        "returns": "str [°C]",
        "tags": ["sat", "saturation", "temperature", "units", "formatted"],
    },
    "bracket": {
        "sig": "bracket(xs, x)",
        "does": "Find bracketing index pair around x for sorted xs.",
        "requires": ["xs [sorted list]", "x [scalar]"],
        "returns": "(i0, i1) [index pair]",
        "tags": ["interpolation", "utility", "index"],
    },
    "fmt": {
        "sig": "fmt(x)",
        "does": "High-precision numeric-to-string formatter using up to 15 significant digits.",
        "requires": ["x [value]"],
        "returns": "formatted [str]",
        "tags": ["units", "formatted", "display", "utility", "precision"],
    },
    "fmt_with_unit": {
        "sig": "fmt_with_unit(x, unit)",
        "does": "Format value with high precision and append unit text.",
        "requires": ["x [value]", "unit [str]"],
        "returns": "formatted [str]",
        "tags": ["units", "formatted", "display", "utility", "precision"],
    },
    "h_Tx": {
        "sig": "h_Tx(T_C, x)",
        "does": "Mixture enthalpy from saturation temperature and quality.",
        "requires": ["T_C [°C]", "x [-]"],
        "returns": "h [kJ/kg]",
        "tags": ["enthalpy", "energy", "quality", "mixture", "sat"],
    },
    "h_Tx_u": {
        "sig": "h_Tx_u(T_C, x)",
        "does": "Formatted mixture enthalpy from temperature and quality.",
        "requires": ["T_C [°C]", "x [-]"],
        "returns": "str [kJ/kg]",
        "tags": ["enthalpy", "energy", "quality", "units", "formatted"],
    },
    "h_pT": {
        "sig": "h_pT(P_kPa, T_C)",
        "does": "Enthalpy at pressure/temperature with automatic region selection.",
        "requires": ["P_kPa [kPa]", "T_C [°C]"],
        "returns": "h [kJ/kg]",
        "tags": ["enthalpy", "energy", "pT", "superheated", "compressed"],
    },
    "h_pT_u": {
        "sig": "h_pT_u(P_kPa, T_C)",
        "does": "Formatted enthalpy at pressure/temperature.",
        "requires": ["P_kPa [kPa]", "T_C [°C]"],
        "returns": "str [kJ/kg]",
        "tags": ["enthalpy", "energy", "pT", "units", "formatted"],
    },
    "help_fn": {
        "sig": "help_fn(name)",
        "does": "Detailed multi-line command help for one function.",
        "requires": ["name [function name]"],
        "returns": "help text [str]",
        "tags": ["help", "docs", "lookup", "discover"],
    },
    "interp1": {
        "sig": "interp1(xs, ys, x)",
        "does": "One-dimensional linear interpolation.",
        "requires": ["xs [sorted list]", "ys [list]", "x [scalar]"],
        "returns": "y [same units as ys]",
        "tags": ["interpolation", "utility", "1d"],
    },
    "lerp": {
        "sig": "lerp(x, x0, x1, y0, y1)",
        "does": "Linear interpolation between two points.",
        "requires": ["x [scalar]", "x0, x1 [scalar]", "y0, y1 [scalar]"],
        "returns": "y [same units as y0/y1]",
        "tags": ["interpolation", "utility", "linear"],
    },
    "list_commands": {
        "sig": "list_commands()",
        "does": "List all public command signatures alphabetically.",
        "requires": [],
        "returns": "signatures [list[str]]",
        "tags": ["help", "docs", "discover", "commands"],
    },
    "lookup": {
        "sig": "lookup(keyword)",
        "does": "Keyword search for function signatures, units, and descriptions.",
        "requires": ["keyword [str]"],
        "returns": "matches [list[str]]",
        "tags": ["help", "docs", "discover", "search", "lookup"],
    },
    "mix": {
        "sig": "mix(prop_f, prop_g, x)",
        "does": "Linear quality blend between saturated liquid and vapor values.",
        "requires": ["prop_f [value]", "prop_g [value]", "x [-]"],
        "returns": "property [same units as inputs]",
        "tags": ["quality", "mixture", "sat"],
    },
    "pSat_T": {
        "sig": "pSat_T(T_C)",
        "does": "Saturation pressure from temperature.",
        "requires": ["T_C [°C]"],
        "returns": "P_sat [kPa]",
        "tags": ["sat", "saturation", "pressure", "temperature", "psat"],
    },
    "pSat_T_u": {
        "sig": "pSat_T_u(T_C)",
        "does": "Formatted saturation pressure from temperature.",
        "requires": ["T_C [°C]"],
        "returns": "str [kPa]",
        "tags": ["sat", "saturation", "pressure", "units", "formatted"],
    },
    "region_pT": {
        "sig": "region_pT(P_kPa, T_C)",
        "does": "Region classification: compressed, two-phase, or superheated.",
        "requires": ["P_kPa [kPa]", "T_C [°C]"],
        "returns": "region [str]",
        "notes": "Two-phase band uses ±0.25 °C around Tsat(P).",
        "tags": ["region", "pT", "sat", "compressed", "superheated"],
    },
    "s_Tx": {
        "sig": "s_Tx(T_C, x)",
        "does": "Mixture entropy from saturation temperature and quality.",
        "requires": ["T_C [°C]", "x [-]"],
        "returns": "s [kJ/kg-K]",
        "tags": ["entropy", "quality", "mixture", "sat"],
    },
    "s_Tx_u": {
        "sig": "s_Tx_u(T_C, x)",
        "does": "Formatted mixture entropy from temperature and quality.",
        "requires": ["T_C [°C]", "x [-]"],
        "returns": "str [kJ/kg-K]",
        "tags": ["entropy", "quality", "units", "formatted"],
    },
    "s_pT": {
        "sig": "s_pT(P_kPa, T_C)",
        "does": "Entropy at pressure/temperature with automatic region selection.",
        "requires": ["P_kPa [kPa]", "T_C [°C]"],
        "returns": "s [kJ/kg-K]",
        "tags": ["entropy", "pT", "superheated", "compressed"],
    },
    "s_pT_u": {
        "sig": "s_pT_u(P_kPa, T_C)",
        "does": "Formatted entropy at pressure/temperature.",
        "requires": ["P_kPa [kPa]", "T_C [°C]"],
        "returns": "str [kJ/kg-K]",
        "tags": ["entropy", "pT", "units", "formatted"],
    },
    "sat_P": {
        "sig": "sat_P(P_kPa)",
        "does": "Saturated state properties at pressure.",
        "requires": ["P_kPa [kPa]"],
        "returns": "sat_props [dict]",
        "tags": ["sat", "saturation", "pressure", "state"],
    },
    "sat_T": {
        "sig": "sat_T(T_C)",
        "does": "Saturated state properties at temperature.",
        "requires": ["T_C [°C]"],
        "returns": "sat_props [dict]",
        "tags": ["sat", "saturation", "temperature", "state"],
    },
    "state": {
        "sig": "state(**known)",
        "does": "Flexible state solver from any supported subset of P_kPa, T_C, x, v, u, h, s.",
        "requires": [
            "known keys: P_kPa [kPa], T_C [°C], x [-], v [m^3/kg], u [kJ/kg], h [kJ/kg], s [kJ/kg-K]"
        ],
        "returns": "state dict [known, region, computed, needs, sat, units, notes]",
        "notes": "Uses deterministic priority: (P,T) -> (T,x) -> (P,x) -> (P,prop) -> (T,prop). See state_help().",
        "tags": ["state", "solver", "flash", "region", "sat", "pT", "quality", "units"],
    },
    "state_help": {
        "sig": "state_help()",
        "does": "Printable TI-friendly usage guide for state() and state_u().",
        "requires": [],
        "returns": "None [prints guide]",
        "tags": ["state", "help", "docs", "solver", "guide", "print"],
    },
    "state_u": {
        "sig": "state_u(**known)",
        "does": "Solve and print formatted state output with units and high precision.",
        "requires": [
            "known keys: P_kPa [kPa], T_C [°C], x [-], v [m^3/kg], u [kJ/kg], h [kJ/kg], s [kJ/kg-K]",
        ],
        "returns": "None [prints formatted state]",
        "tags": ["state", "solver", "units", "formatted", "display", "print"],
    },
    "u_Tx": {
        "sig": "u_Tx(T_C, x)",
        "does": "Mixture internal energy from saturation temperature and quality.",
        "requires": ["T_C [°C]", "x [-]"],
        "returns": "u [kJ/kg]",
        "tags": ["energy", "internal", "quality", "mixture", "sat"],
    },
    "u_Tx_u": {
        "sig": "u_Tx_u(T_C, x)",
        "does": "Formatted mixture internal energy from temperature and quality.",
        "requires": ["T_C [°C]", "x [-]"],
        "returns": "str [kJ/kg]",
        "tags": ["energy", "internal", "quality", "units", "formatted"],
    },
    "u_pT": {
        "sig": "u_pT(P_kPa, T_C)",
        "does": "Internal energy at pressure/temperature with automatic region selection.",
        "requires": ["P_kPa [kPa]", "T_C [°C]"],
        "returns": "u [kJ/kg]",
        "tags": ["energy", "internal", "u", "pT", "superheated", "compressed"],
    },
    "u_pT_u": {
        "sig": "u_pT_u(P_kPa, T_C)",
        "does": "Formatted internal energy at pressure/temperature.",
        "requires": ["P_kPa [kPa]", "T_C [°C]"],
        "returns": "str [kJ/kg]",
        "tags": ["energy", "internal", "pT", "units", "formatted"],
    },
    "v_Tx": {
        "sig": "v_Tx(T_C, x)",
        "does": "Mixture specific volume from saturation temperature and quality.",
        "requires": ["T_C [°C]", "x [-]"],
        "returns": "v [m^3/kg]",
        "tags": ["volume", "mass", "quality", "mixture", "sat"],
    },
    "v_Tx_u": {
        "sig": "v_Tx_u(T_C, x)",
        "does": "Formatted mixture specific volume from temperature and quality.",
        "requires": ["T_C [°C]", "x [-]"],
        "returns": "str [m^3/kg]",
        "tags": ["volume", "mass", "quality", "units", "formatted"],
    },
    "v_pT": {
        "sig": "v_pT(P_kPa, T_C)",
        "does": "Specific volume at pressure/temperature with automatic region selection.",
        "requires": ["P_kPa [kPa]", "T_C [°C]"],
        "returns": "v [m^3/kg]",
        "tags": ["volume", "mass", "pT", "superheated", "compressed"],
    },
    "v_pT_u": {
        "sig": "v_pT_u(P_kPa, T_C)",
        "does": "Formatted specific volume at pressure/temperature.",
        "requires": ["P_kPa [kPa]", "T_C [°C]"],
        "returns": "str [m^3/kg]",
        "tags": ["volume", "mass", "pT", "units", "formatted"],
    },
    "with_units": {
        "sig": "with_units(func_name, *args)",
        "does": "Call function by name and return a units-formatted output string.",
        "requires": ["func_name [str]", "*args [function args]"],
        "returns": "formatted output [str]",
        "tags": ["units", "formatted", "display", "wrapper"],
    },
    "x_from_h": {
        "sig": "x_from_h(h, hf, hg)",
        "does": "Quality from enthalpy and saturation endpoints.",
        "requires": ["h [kJ/kg]", "hf [kJ/kg]", "hg [kJ/kg]"],
        "returns": "x [-]",
        "tags": ["quality", "enthalpy", "mixture"],
    },
    "x_from_s": {
        "sig": "x_from_s(s, sf, sg)",
        "does": "Quality from entropy and saturation endpoints.",
        "requires": ["s [kJ/kg-K]", "sf [kJ/kg-K]", "sg [kJ/kg-K]"],
        "returns": "x [-]",
        "tags": ["quality", "entropy", "mixture"],
    },
    "x_from_u": {
        "sig": "x_from_u(u, uf, ug)",
        "does": "Quality from internal energy and saturation endpoints.",
        "requires": ["u [kJ/kg]", "uf [kJ/kg]", "ug [kJ/kg]"],
        "returns": "x [-]",
        "tags": ["quality", "energy", "internal", "mixture"],
    },
    "x_from_v": {
        "sig": "x_from_v(v, vf, vg)",
        "does": "Quality from specific volume and saturation endpoints.",
        "requires": ["v [m^3/kg]", "vf [m^3/kg]", "vg [m^3/kg]"],
        "returns": "x [-]",
        "tags": ["quality", "volume", "mass", "mixture"],
    },
}


__all__ = [
    "bracket",
    "lerp",
    "interp1",
    "sat_T",
    "sat_P",
    "pSat_T",
    "Tsat_p",
    "mix",
    "x_from_v",
    "x_from_u",
    "x_from_h",
    "x_from_s",
    "u_Tx",
    "h_Tx",
    "s_Tx",
    "v_Tx",
    "region_pT",
    "u_pT",
    "h_pT",
    "s_pT",
    "v_pT",
    "fmt",
    "fmt_with_unit",
    "with_units",
    "u_pT_u",
    "h_pT_u",
    "s_pT_u",
    "v_pT_u",
    "pSat_T_u",
    "Tsat_p_u",
    "u_Tx_u",
    "h_Tx_u",
    "s_Tx_u",
    "v_Tx_u",
    "state",
    "state_u",
    "state_help",
    "lookup",
    "help_fn",
    "list_commands",
]
