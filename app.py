import os
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.interpolate import interp1d

from ahu_vav_system.zone import Zone
from ahu_vav_system.vav import VAV
from ahu_vav_system.ahu import AHU
from ahu_vav_system.single_zone import SingleZone
from weather import Weather

INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "input_files")
DEFAULT_CITY = "Ottawa"
# The EPW file is a typical year (8760 h, no leap day), so the dates are restricted to one non-leap year.
YEAR = 2023


def weather_files():
    """EPW files in the input folder as {label: path}, e.g. 'Ottawa, ON'.

    The label comes from the file name (CAN_<province>_<city>...epw).
    """
    files = {}
    for name in os.listdir(INPUT_DIR):
        if not name.lower().endswith(".epw"):
            continue
        parts = name.split("_")
        if len(parts) >= 3:
            city = parts[2].split(".")[0].replace("-", " ")
            label = f"{city.title() if city.isupper() else city}, {parts[1]}"
        else:
            label = os.path.splitext(name)[0]
        files[label] = os.path.join(INPUT_DIR, name)
    return dict(sorted(files.items()))


def run_simulation(weather, start, end, p):
    """Run the AHU + VAV + zone model from start to end (hourly, both inclusive).

    p is a dict of the model inputs (see `sidebar_inputs`). Returns the outdoor
    temperature series, the simulation results and the zone setpoint.
    """
    T_out_series = weather.temperature_between(start, end)
    n = len(T_out_series)
    t_series = np.arange(0, n * 3600, 3600)

    def interp(values):
        return interp1d(t_series, values, fill_value="extrapolate")

    T_out_f   = interp(T_out_series)
    Q_gains_f = interp(np.full(n, p["Q_gains"]))
    Q_rad_f   = interp(np.full(n, p["Q_rad"]))
    Q_coil_f  = interp(np.full(n, p["Q_coil"]))

    ctrl = dict(T_set=p["T_set"], Kp=p["Kp"], msa_min=p["msa_min"], msa_max=p["msa_max"],
                direction=p["direction"])
    zone = Zone(p["C"], p["R"], Q_gains_f)
    vav  = VAV(ctrl, Q_rad_f)
    ahu  = AHU(Q_coil_f, p["T_sasp"], foa_min=p["foa_min"], foa0=p["foa0"])
    model = SingleZone(zone, vav, ahu, T_out_f)

    res = model.simulate(t_series, p["T_in0"])
    return T_out_series, res, vav.T_set


def make_figure(times, T_out_series, res, T_set):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=[9, 9], sharex=True)

    ax1.plot(times, res["T_in"], label="Indoor temp")
    ax1.plot(times, T_out_series, label="Outdoor temp", ls="--")
    ax1.axhline(T_set, color="k", ls=":", label="Setpoint")
    ax1.set_ylabel("Temperature [°C]")
    ax1.legend(frameon=False)

    ax2.plot(times, res["msa"])
    ax2.set_ylabel("Supply air flow [L/s]")

    ax3.step(times, res["foa"], where="post")
    ax3.set_ylabel("Outdoor air fraction [-]")
    ax3.set_xlabel("Time")

    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    fig.tight_layout()
    return fig


def sidebar_inputs():
    """Draw the input form in the sidebar. Returns (epw_path, start_date, end_date, params)."""
    cities = weather_files()
    labels = list(cities)
    default = next((i for i, c in enumerate(labels) if c.startswith(DEFAULT_CITY)), 0)

    with st.sidebar.form("inputs"):
        st.subheader("Weather")
        city = st.selectbox("City", labels, index=default)

        st.subheader("Period")
        start_date = st.date_input("Start date", value=date(YEAR, 6, 1),
                                   min_value=date(YEAR, 1, 1), max_value=date(YEAR, 12, 31))
        end_date = st.date_input("End date (inclusive)", value=date(YEAR, 6, 7),
                                 min_value=date(YEAR, 1, 1), max_value=date(YEAR, 12, 31))
        st.caption("The weather file is a typical year, so the year is ignored.")

        st.subheader("Building")
        C = st.number_input("Thermal capacitance C [MJ/K]", value=5.0, min_value=0.1, step=0.5)
        R = st.number_input("Thermal resistance R [K/W]", value=0.01, min_value=0.0001,
                            step=0.001, format="%.4f")
        T_in0 = st.number_input("Initial indoor temperature [°C]", value=20.0, step=0.5)
        Q_gains = st.number_input("Internal gains [W]", value=500.0, step=50.0)

        st.subheader("AHU")
        Q_coil = st.number_input("Coil heat [W]  (+ heating, − cooling)", value=1200.0, step=100.0)
        T_sasp = st.number_input("Supply air temperature setpoint [°C]", value=18.0, step=0.5)
        foa_min = st.number_input("Minimum outdoor air fraction [-]", value=0.2,
                                  min_value=0.0, max_value=1.0, step=0.05)
        foa0 = st.number_input("Initial outdoor air fraction [-]", value=0.2,
                               min_value=0.0, max_value=1.0, step=0.05)

        st.subheader("VAV")
        Q_rad = st.number_input("Reheat coil heat [W]", value=1000.0, step=100.0)
        T_set = st.number_input("Zone temperature setpoint [°C]", value=22.0, step=0.5)
        Kp = st.number_input("Controller gain Kp [L/s per K]", value=20.0, min_value=0.0, step=1.0)
        msa_min = st.number_input("Minimum supply air flow [L/s]", value=10.0, min_value=0.1, step=5.0)
        msa_max = st.number_input("Maximum supply air flow [L/s]", value=800.0, min_value=0.1, step=50.0)
        mode = st.selectbox("Control action", ["Heating (more flow when zone is cold)",
                                               "Cooling (more flow when zone is hot)"])

        st.form_submit_button("Run simulation")

    params = dict(
        C=C * 1e6, R=R, T_in0=T_in0, Q_gains=Q_gains,
        Q_coil=Q_coil, T_sasp=T_sasp, foa_min=foa_min, foa0=foa0,
        Q_rad=Q_rad, T_set=T_set, Kp=Kp, msa_min=msa_min, msa_max=msa_max,
        direction=-1 if mode.startswith("Heating") else 1,
    )
    return cities[city], start_date, end_date, params


def main():
    st.set_page_config(page_title="AHU-VAV zone model", layout="wide")
    st.title("Single zone with VAV and AHU")

    epw_path, start_date, end_date, params = sidebar_inputs()

    if end_date < start_date:
        st.error("The end date must not be before the start date.")
        st.stop()
    if params["msa_min"] > params["msa_max"]:
        st.error("The minimum supply air flow must not exceed the maximum.")
        st.stop()

    start = datetime.combine(start_date, time(0))
    end   = datetime.combine(end_date, time(23))
    n_hours = int((end - start).total_seconds() // 3600) + 1

    try:
        weather = Weather(epw_path)
        with st.spinner(f"Simulating {n_hours} hours..."):
            T_out_series, res, T_set = run_simulation(weather, start, end, params)
    except Exception as e:
        st.error(f"Could not run the simulation: {e}")
        st.stop()

    times = [start + timedelta(hours=i) for i in range(n_hours)]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Indoor min [°C]", f"{res['T_in'].min():.1f}")
    c2.metric("Indoor mean [°C]", f"{res['T_in'].mean():.1f}")
    c3.metric("Indoor max [°C]", f"{res['T_in'].max():.1f}")
    c4.metric("Peak supply flow [L/s]", f"{res['msa'].max():.0f}")

    st.pyplot(make_figure(times, T_out_series, res, T_set))

    df = pd.DataFrame({
        "time": times,
        "T_out [C]": T_out_series,
        "T_in [C]": res["T_in"],
        "msa [L/s]": res["msa"],
        "foa [-]": res["foa"],
    })
    with st.expander("Results table"):
        st.dataframe(df)
    st.download_button("Download results (CSV)", df.to_csv(index=False), file_name="results.csv")


if __name__ == "__main__":
    main()
