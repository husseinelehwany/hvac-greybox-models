import os
from datetime import datetime, timedelta
import time

import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d

from hvac_greybox import PROJECT_ROOT
from hvac_greybox.weather import Weather
from hvac_greybox.zones import Zone2R2C
from hvac_greybox.equipment import AHU, VAV
from hvac_greybox.controllers import DeadbandPController
from hvac_greybox.systems import AHUVAVTwoZones
from hvac_greybox.plotting import plot_ahu_vav, plot_foa_vs_toa

WEATHER_DIR = os.path.join(PROJECT_ROOT, "data", "weather")

# --- Read outdoor temperature and solar irradiance from EPW for the simulated period ---
weather = Weather(os.path.join(WEATHER_DIR, "CAN_ON_Ottawa.716280_CWEC.epw"))
start = datetime(2023, 4, 1, 0)    # first simulated hour
end   = datetime(2023, 4, 30, 23)   # last simulated hour (inclusive)
T_out_series_h = weather.temperature_between(start, end)   # hourly from weather file [°C]
I_sol_series_h = weather.get_ghi(start, end)              # hourly global horizontal irradiance [W/m²]

# Effective solar aperture (A_win·SHGC·F_orient·F_shade) of each zone [m²]
A_eff_a = 2.0    # zone a: sunny side
A_eff_b = 0.5    # zone b: shaded side
Q_sol_a_series_h = A_eff_a * I_sol_series_h   # hourly solar heat gain, zone a [W]
Q_sol_b_series_h = A_eff_b * I_sol_series_h   # hourly solar heat gain, zone b [W]

# --- Time ---
n_hours = len(T_out_series_h)                    # number of hourly samples
t_series_h = np.arange(0, n_hours * 3600, 3600)  # used with the hourly weather series
t_series = np.arange(0, n_hours * 3600, 15*60)  # time since start, in seconds
n = len(t_series)

# --- Zone parameters (2R2C: air node + internal mass node) ---
C_in  = 5e5      # air node thermal capacitance [J/K]
C_m   = 4.5e6    # internal mass thermal capacitance [J/K]
R_out = 0.01     # resistance outdoors <-> indoor air [K/W]
R_m   = 0.002    # resistance indoor air <-> mass [K/W]
T_in0_a = 20.0   # initial temperature of zone a [°C] (air and mass)
T_in0_b = 20.0   # initial temperature of zone b [°C] (air and mass)
Q_gains_a_series = np.full(n, 250.0)   # constant internal gains, zone a [W]
Q_gains_b_series = np.full(n, 250.0)   # constant internal gains, zone b [W]

# --- Control actuators ---
f_oa = 0.2

# VAVs: deadband P control on each zone's temperature
# above setpoint + deadband/2 -> flow ramps from msa_min to msa_max (cooling)
# below setpoint - deadband/2 -> flow at msa_min, baseboard heater ramps to Q_rad_rated (heating)
vav_ctrl_a = DeadbandPController(setpoint=22.0, deadband=2.0, Kp_cool=0.5, Kp_heat=0.5)
vav_ctrl_b = DeadbandPController(setpoint=22.0, deadband=2.0, Kp_cool=0.5, Kp_heat=0.5)
msa_min, msa_max = 10.0, 800.0   # supply air flow limits of each VAV [L/s]
Q_rad_rated = 1000.0             # rated baseboard heater output of each zone [W]

# AHU coil and economizer (serves both VAVs, so sized for two zones)
Q_coil_rated = 2400.0   # rated coil heat transfer, limits the coil output both ways [W]
Kp_coil = 1000.0        # coil controller gain on the supply air temperature error [W/K]
T_sasp = 18.0           # supply air temperature setpoint [°C]

# Interpolators, built once and reused every time step
T_out_f     = interp1d(t_series_h, T_out_series_h,    fill_value="extrapolate")
T_out_series = T_out_f(t_series)
Q_sol_a_f   = interp1d(t_series_h, Q_sol_a_series_h,  fill_value="extrapolate")
Q_sol_b_f   = interp1d(t_series_h, Q_sol_b_series_h,  fill_value="extrapolate")
Q_gains_a_f = interp1d(t_series,   Q_gains_a_series,  fill_value="extrapolate")
Q_gains_b_f = interp1d(t_series,   Q_gains_b_series,  fill_value="extrapolate")

# --- Build and run the model ---
zone_a = Zone2R2C(C_in, C_m, R_out, R_m, Q_sol_a_f, Q_gains_a_f)
zone_b = Zone2R2C(C_in, C_m, R_out, R_m, Q_sol_b_f, Q_gains_b_f)
vav_a  = VAV(vav_ctrl_a, msa_min, msa_max, Q_rad_rated)
vav_b  = VAV(vav_ctrl_b, msa_min, msa_max, Q_rad_rated)
ahu    = AHU(Q_coil_rated, T_sasp, Kp_coil=Kp_coil, foa_min=0.2, foa0=f_oa)
start_time = time.time()
model = AHUVAVTwoZones(zone_a, zone_b, vav_a, vav_b, ahu, T_out_f)
res = model.simulate(t_series, T_in0_a, T_in0_b)
end_time = time.time()
elapsed_time = end_time - start_time
print(f"Elapsed time = {elapsed_time:.2f} seconds!")


def zone_view(res, z):
    """Results of zone z ('a' or 'b') under the single-zone keys used by the plot functions.

    Zone values (T_in, msa, Q_rad, Q_vav) are that zone's; AHU values (foa, T_sa, Q_coil)
    are shared by both zones.
    """
    view = {key: res[key] for key in ("t", "foa", "T_sa", "Q_coil")}
    for key in ("T_in", "T_m", "msa", "Q_rad", "Q_vav"):
        view[key] = res[f"{key}_{z}"]
    return view


times = [start + timedelta(seconds=float(s)) for s in res["t"]]
for z, ctrl in (("a", vav_ctrl_a), ("b", vav_ctrl_b)):
    fig = plot_ahu_vav(times, zone_view(res, z), T_out_series, ctrl.sp_heat, ctrl.sp_cool)
    fig.suptitle(f"Zone {z}")
    fig.tight_layout()

# Economizer: the AHU sees the mixed return air, so colour by T_ra rather than one zone's T_in
fig = plot_foa_vs_toa({"foa": res["foa"], "T_in": res["T_ra"]}, T_out_series)
plt.show()
