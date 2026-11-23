import os
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
import streamlit as st
from scipy.interpolate import interp1d

from hvac_greybox import PROJECT_ROOT
from hvac_greybox.weather import Weather
from hvac_greybox.zones import Zone2R2C
from hvac_greybox.equipment import AHU, VAV
from hvac_greybox.controllers import DeadbandPController
from hvac_greybox.systems import AHUVAVTwoZones
from hvac_greybox.plotting import plot_ahu_vav_two_zones, plot_foa_vs_toa
from hvac_greybox.gui import zone_2r2c_svg, ahu_svg, vav_svg, show

WEATHER_DIR = os.path.join(PROJECT_ROOT, "data", "weather")
DEFAULT_CITY = "Ottawa"
# The EPW file is a typical year (8760 h, no leap day), so the dates are restricted to one non-leap year.
YEAR = 2023
ZONES = ("a", "b")


def weather_files():
    """EPW files in the weather folder as {label: path}, e.g. 'Ottawa, ON'.

    The label comes from the file name (CAN_<province>_<city>...epw).
    """
    files = {}
    for name in os.listdir(WEATHER_DIR):
        if not name.lower().endswith(".epw"):
            continue
        parts = name.split("_")
        if len(parts) >= 3:
            city = parts[2].split(".")[0].replace("-", " ")
            label = f"{city.title() if city.isupper() else city}, {parts[1]}"
        else:
            label = os.path.splitext(name)[0]
        files[label] = os.path.join(WEATHER_DIR, name)
    return dict(sorted(files.items()))


def run_simulation(weather, start, end, p):
    """Run the AHU + two VAVs + two 2R2C zones model from start to end (hourly, both inclusive).

    p is a dict of the model inputs (see `input_tab`): p["ahu"], p["a"] and p["b"].
    Returns the outdoor temperature series, the simulation results and the VAV
    controllers {zone: controller}.
    """
    T_out_series = weather.temperature_between(start, end)
    ghi = weather.get_ghi(start, end)
    n = len(T_out_series)
    t_series = np.arange(0, n * 3600, 3600)

    def interp(values):
        return interp1d(t_series, values, fill_value="extrapolate")

    T_out_f = interp(T_out_series)

    zones, vavs, ctrls = {}, {}, {}
    for z in ZONES:
        pz = p[z]
        Q_sol_f   = interp(pz["A_eff"] * ghi)                 # solar gain [W]
        Q_gains_f = interp(np.full(n, pz["Q_gains"]))         # internal gains [W]
        ctrls[z] = DeadbandPController(setpoint=pz["T_set"], deadband=pz["deadband"],
                                       Kp_cool=pz["Kp_cool"], Kp_heat=pz["Kp_heat"])
        zones[z] = Zone2R2C(pz["C_in"], pz["C_m"], pz["R_out"], pz["R_m"], Q_sol_f, Q_gains_f)
        vavs[z] = VAV(ctrls[z], pz["msa_min"], pz["msa_max"], pz["Q_rad_rated"])

    pa = p["ahu"]
    ahu = AHU(pa["Q_coil_rated"], pa["T_sasp"], Kp_coil=pa["Kp_coil"],
              foa_min=pa["foa_min"], foa0=pa["foa0"])
    model = AHUVAVTwoZones(zones["a"], zones["b"], vavs["a"], vavs["b"], ahu, T_out_f)

    res = model.simulate(t_series, p["a"]["T_in0"], p["b"]["T_in0"])
    return T_out_series, res, ctrls


# Default input values. Zone inputs are stored per zone with a suffix (e.g. "R_out_a"),
# AHU inputs without one. The schematics read the current values from st.session_state
# (keyed like these), falling back to the defaults before the form is first submitted.
ZONE_DEFAULTS = dict(
    A_eff=2.0, R_out=0.01, R_m=0.002, C_in_MJ=0.5, C_m_MJ=4.5, T_in0=20.0, Q_gains=500.0,
    T_set=22.0, deadband=2.0, Kp_cool=0.5, Kp_heat=0.5,
    msa_min=10.0, msa_max=800.0, Q_rad_rated=1000.0,
)
ZONE_OVERRIDES = {"b": dict(A_eff=0.5)}   # zone b: shaded side
AHU_DEFAULTS = dict(foa_min=0.2, foa0=0.2, Q_coil_rated=2400.0, Kp_coil=1000.0, T_sasp=18.0)

DEFAULTS = dict(AHU_DEFAULTS)
for _z in ZONES:
    for _k, _d in ZONE_DEFAULTS.items():
        DEFAULTS[f"{_k}_{_z}"] = ZONE_OVERRIDES.get(_z, {}).get(_k, _d)


def current_values():
    """Input values as last submitted (defaults on the first run)."""
    try:
        state = st.session_state
        return {k: state[k] if k in state else d for k, d in DEFAULTS.items()}
    except Exception:   # no session state, e.g. when run as a plain script
        return dict(DEFAULTS)


def zone_values(v, z):
    """Values of zone z from v, without the zone suffix (as the schematics expect)."""
    return {k: v[f"{k}_{z}"] for k in ZONE_DEFAULTS}


def num(label, key, **kwargs):
    """Number input whose default and session-state key come from DEFAULTS."""
    return st.number_input(label, value=DEFAULTS[key], key=key, **kwargs)


def zone_inputs(z, v):
    """Schematics and inputs of zone z and its VAV box. Returns that zone's parameters."""
    name = f"Zone {z}"
    vz = zone_values(v, z)
    with st.expander(f"{name} and VAV {z}", expanded=True):
        show(zone_2r2c_svg(vz, name))
        st.markdown("**Envelope and thermal mass**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            R_out = num("R_out [K/W]", f"R_out_{z}", min_value=0.0001, step=0.001, format="%.4f",
                        help="Thermal resistance between outdoors and indoor air (= 1/UA)")
        with c2:
            R_m = num("R_m [K/W]", f"R_m_{z}", min_value=0.0001, step=0.001, format="%.4f",
                      help="Thermal resistance between indoor air and the internal mass")
        with c3:
            C_in_MJ = num("C_in [MJ/K]", f"C_in_MJ_{z}", min_value=0.01, step=0.1,
                          help="Thermal capacitance of the indoor air node")
        with c4:
            C_m_MJ = num("C_m [MJ/K]", f"C_m_MJ_{z}", min_value=0.1, step=0.5,
                         help="Thermal capacitance of the internal mass node")
        st.markdown("**Loads and initial state**")
        c1, c2, c3 = st.columns(3)
        with c1:
            A_eff = num("A_eff [m²]", f"A_eff_{z}", min_value=0.0, step=0.5,
                        help="Effective solar aperture: solar gain = A_eff × GHI")
        with c2:
            Q_gains = num("Internal gains [W]", f"Q_gains_{z}", step=50.0,
                          help="Constant gains from people and equipment")
        with c3:
            T_in0 = num("T_in(0) [°C]", f"T_in0_{z}", step=0.5,
                        help="Initial temperature of the air and the mass")
        st.markdown("**Thermostat**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            T_set = num("Zone setpoint [°C]", f"T_set_{z}", step=0.5)
        with c2:
            deadband = num("Deadband [K]", f"deadband_{z}", min_value=0.0, step=0.5)
        with c3:
            Kp_cool = num("Cooling gain [1/K]", f"Kp_cool_{z}", min_value=0.0, step=0.1,
                          help="Full VAV flow 1/Kp above the deadband")
        with c4:
            Kp_heat = num("Heating gain [1/K]", f"Kp_heat_{z}", min_value=0.0, step=0.1,
                          help="Full baseboard heat 1/Kp below the deadband")

        st.markdown(f"**VAV box {z}**")
        show(vav_svg(vz, name))
        c1, c2, c3 = st.columns(3)
        with c1:
            msa_min = num("Min flow [L/s]", f"msa_min_{z}", min_value=0.1, step=5.0)
        with c2:
            msa_max = num("Max flow [L/s]", f"msa_max_{z}", min_value=0.1, step=50.0)
        with c3:
            Q_rad_rated = num("Baseboard rated [W]", f"Q_rad_rated_{z}", min_value=0.0, step=100.0)

    return dict(
        R_out=R_out, R_m=R_m, C_in=C_in_MJ * 1e6, C_m=C_m_MJ * 1e6,
        A_eff=A_eff, Q_gains=Q_gains, T_in0=T_in0,
        T_set=T_set, deadband=deadband, Kp_cool=Kp_cool, Kp_heat=Kp_heat,
        msa_min=msa_min, msa_max=msa_max, Q_rad_rated=Q_rad_rated,
    )


def input_tab():
    """Weather, period, the inputs of each zone with its VAV, and the AHU inputs.

    Returns (epw_path, start_date, end_date, params).
    """
    cities = weather_files()
    labels = list(cities)
    default = next((i for i, c in enumerate(labels) if c.startswith(DEFAULT_CITY)), 0)
    v = current_values()

    with st.form("inputs"):
        st.subheader("Weather and period")
        c1, c2, c3 = st.columns([2, 1, 1])
        city = c1.selectbox("City", labels, index=default)
        start_date = c2.date_input("Start date", value=date(YEAR, 6, 1),
                                   min_value=date(YEAR, 1, 1), max_value=date(YEAR, 12, 31))
        end_date = c3.date_input("End date (inclusive)", value=date(YEAR, 6, 7),
                                 min_value=date(YEAR, 1, 1), max_value=date(YEAR, 12, 31))
        st.caption("The weather file is a typical year, so the year is ignored.")

        # --- Zones, each with its VAV box ---
        st.subheader("Zones")
        params = {z: zone_inputs(z, v) for z in ZONES}

        # --- AHU, serving both VAV boxes ---
        st.subheader("Air handling unit (serves both VAV boxes)")
        show(ahu_svg(v))
        c1, c2, c3 = st.columns([3, 2, 3])
        with c1:
            foa_min = num("Min outdoor air fraction [-]", "foa_min",
                          min_value=0.0, max_value=1.0, step=0.05)
            foa0 = num("Initial outdoor air fraction [-]", "foa0",
                       min_value=0.0, max_value=1.0, step=0.05)
        with c2:
            Q_coil_rated = num("Coil rated heat [W]", "Q_coil_rated", min_value=0.0, step=100.0,
                               help="Limits both heating and cooling")
            Kp_coil = num("Coil gain Kp [W/K]", "Kp_coil", min_value=0.0, step=100.0,
                          help="P controller gain on the supply air temperature error")
        with c3:
            T_sasp = num("Supply air setpoint [°C]", "T_sasp", step=0.5)

        st.form_submit_button("Run simulation")
        st.caption("After running, open the Results tab.")

    params["ahu"] = dict(Q_coil_rated=Q_coil_rated, Kp_coil=Kp_coil, T_sasp=T_sasp,
                         foa_min=foa_min, foa0=foa0)
    return cities[city], start_date, end_date, params


def results_tab(epw_path, start_date, end_date, params):
    """Run the simulation and show the metrics, plots and results table."""
    if end_date < start_date:
        st.error("The end date must not be before the start date.")
        return
    for z in ZONES:
        if params[z]["msa_min"] > params[z]["msa_max"]:
            st.error(f"Zone {z}: the minimum supply air flow must not exceed the maximum.")
            return

    start = datetime.combine(start_date, time(0))
    end   = datetime.combine(end_date, time(23))
    n_hours = int((end - start).total_seconds() // 3600) + 1

    try:
        weather = Weather(epw_path)
        with st.spinner(f"Simulating {n_hours} hours..."):
            T_out_series, res, ctrls = run_simulation(weather, start, end, params)
    except Exception as e:
        st.error(f"Could not run the simulation: {e}")
        return

    times = [start + timedelta(hours=i) for i in range(n_hours)]

    for z in ZONES:
        st.markdown(f"**Zone {z}**")
        T_in = res[f"T_in_{z}"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Indoor min [°C]", f"{T_in.min():.1f}")
        c2.metric("Indoor mean [°C]", f"{T_in.mean():.1f}")
        c3.metric("Indoor max [°C]", f"{T_in.max():.1f}")
        c4.metric("Peak VAV flow [L/s]", f"{res[f'msa_{z}'].max():.0f}")
    st.markdown("**AHU**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Peak total flow [L/s]", f"{res['msa'].max():.0f}")
    c2.metric("Mean outdoor air fraction [-]", f"{res['foa'].mean():.2f}")
    c3.metric("Mean return air [°C]", f"{res['T_ra'].mean():.1f}")

    sp = {z: (ctrls[z].sp_heat, ctrls[z].sp_cool) for z in ZONES}
    st.pyplot(plot_ahu_vav_two_zones(times, res, T_out_series, sp["a"], sp["b"]))
    # the economizer sees the mixed return air, so colour by T_ra
    st.pyplot(plot_foa_vs_toa({"foa": res["foa"], "T_in": res["T_ra"]}, T_out_series))

    columns = {
        "time": times,
        "T_out [C]": T_out_series,
        "T_sa [C]": res["T_sa"],
        "T_ra [C]": res["T_ra"],
        "msa total [L/s]": res["msa"],
        "foa [-]": res["foa"],
        "Q_coil [W]": res["Q_coil"],
    }
    for z in ZONES:
        columns.update({
            f"T_in_{z} [C]": res[f"T_in_{z}"],
            f"T_m_{z} [C]": res[f"T_m_{z}"],
            f"msa_{z} [L/s]": res[f"msa_{z}"],
            f"Q_rad_{z} [W]": res[f"Q_rad_{z}"],
            f"Q_vav_{z} [W]": res[f"Q_vav_{z}"],
        })
    df = pd.DataFrame(columns)
    with st.expander("Results table"):
        st.dataframe(df)
    st.download_button("Download results (CSV)", df.to_csv(index=False), file_name="results.csv")


def main():
    st.set_page_config(page_title="AHU-VAV two-zone model", layout="centered")
    st.title("Two zones with VAV boxes and AHU")

    tab_inputs, tab_results = st.tabs(["Inputs", "Results"])
    with tab_inputs:
        inputs = input_tab()
    with tab_results:
        results_tab(*inputs)


if __name__ == "__main__":
    main()
