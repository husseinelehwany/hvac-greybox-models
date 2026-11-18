import os
from datetime import datetime, timedelta
import time
import numpy as np
from scipy.interpolate import interp1d

from ahu_vav_system.zone import Zone
from ahu_vav_system.vav import VAV
from ahu_vav_system.ahu import AHU
from ahu_vav_system.single_zone import SingleZone
from ahu_vav_system.output_plots import plot_ahu_vav, plot_foa_vs_toa
import matplotlib.pyplot as plt
from weather import Weather
from controllers.deadband_p_controller import DeadbandPController

# --- Read outdoor temperature and solar irradiance from EPW for the simulated period ---
weather = Weather(os.path.join("input_files", "CAN_ON_Ottawa.716280_CWEC.epw"))
start = datetime(2023, 4, 1, 0)    # first simulated hour
end   = datetime(2023, 4, 30, 23)   # last simulated hour (inclusive)
T_out_series_h = weather.temperature_between(start, end)   # hourly from weather file [°C]
I_sol_series_h = weather.get_ghi(start, end)              # hourly global horizontal irradiance [W/m²]
A_eff = 2.0                                                # effective solar aperture (A_win·SHGC·F_orient·F_shade) [m²]
Q_sol_series_h = A_eff * I_sol_series_h                    # hourly solar heat gain [W]

# --- Parameters ---
C = 5e6        # thermal capacitance [J/K]
R = 0.01       # thermal resistance [K/W]  (= 1/UA)
T_in0 = 20.0  # initial indoor temperature [°C]
n_hours = len(T_out_series_h)                    # number of hourly samples
t_series_h = np.arange(0, n_hours * 3600, 3600)  # used with T_out_series
t_series = np.arange(0, n_hours * 3600, 15*60)  # time since start, in seconds
n = len(t_series)
Q_gains_series = np.array([250] * n)   # 500 W constant internal gains

# --- Control actuators ---
f_oa = 0.2

# VAV: deadband P control on zone temperature
# above setpoint + deadband/2 -> flow ramps from msa_min to msa_max (cooling)
# below setpoint - deadband/2 -> flow at msa_min, reheat ramps to Q_rad_rated (heating)
vav_ctrl = DeadbandPController(setpoint=22.0, deadband=2.0, Kp_cool=0.5, Kp_heat=0.5)
msa_min, msa_max = 10.0, 800.0   # supply air flow limits [L/s]
Q_rad_rated = 1000.0             # rated reheat coil heat [W]

# AHU coil and economizer
Q_coil_rated = 1200.0   # rated coil heat transfer, limits the coil output both ways [W]
Kp_coil = 1000.0        # coil controller gain on the supply air temperature error [W/K]
T_sasp = 18.0           # supply air temperature setpoint [°C]

# Interpolators, built once and reused by every ODE evaluation
T_out_f   = interp1d(t_series_h, T_out_series_h,   fill_value="extrapolate")
T_out_series = T_out_f(t_series)
I_sol_f   = interp1d(t_series_h, I_sol_series_h,   fill_value="extrapolate")
Q_gains_f   = interp1d(t_series, Q_gains_series,   fill_value="extrapolate")

# --- Build and run the model ---
zone = Zone(C, R, I_sol_f, Q_gains_f)
vav  = VAV(vav_ctrl, msa_min, msa_max, Q_rad_rated)
ahu  = AHU(Q_coil_rated, T_sasp, Kp_coil=Kp_coil, foa_min=0.2, foa0=f_oa)
start_time = time.time()
model = SingleZone(zone, vav, ahu, T_out_f)
res = model.simulate(t_series, T_in0)
end_time = time.time()
elapsed_time = end_time - start_time
print(f"Elapsed time = {elapsed_time:.2f} seconds!")


times    = [start + timedelta(seconds=float(s)) for s in res["t"]]
plot_ahu_vav(times, res, T_out_series, vav_ctrl.sp_heat, vav_ctrl.sp_cool)
plot_foa_vs_toa(res, T_out_series)
plt.show()
