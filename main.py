import os
import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

from ahu_vav_system.zone import Zone
from ahu_vav_system.vav import VAV
from ahu_vav_system.ahu import AHU
from ahu_vav_system.single_zone import SingleZone

# --- Read outdoor temperature from EPW ---
epw_path = os.path.join("input_files", "CAN_ON_Ottawa.716280_CWEC.epw")
with open(epw_path, "r") as f:
    lines = f.readlines()[8:]  # skip 8 header lines
T_out_series = np.array([float(line.split(",")[6]) for line in lines if line.strip()])

# --- Parameters ---
C = 5e6        # thermal capacitance [J/K]
R = 0.01       # thermal resistance [K/W]  (= 1/UA)
T_in0 = 20.0  # initial indoor temperature [°C]
n = 24*7 #len(T_out_series)
T_out_series = T_out_series[0:n]                   # 8760 hours
t_series = np.arange(0, n * 3600, 3600)  # 0 to 8759 h in seconds
Q_gains_series = np.array([500] * n)   # 500 W constant internal gains

# --- Control actuators ---
f_oa = 0.2
Q_coil_series  = np.array([1200]   * n)
Q_rad_series  = np.array([1000]   * n)

# Proportional controller (direction=-1: more flow when zone is below setpoint, i.e. heating)
ctrl = dict(T_set=22.0, Kp=20.0, msa_min=10.0, msa_max=800, direction=-1)

# Economizer
T_sasp = 18.0   # supply air temperature setpoint [°C]

# Interpolators, built once and reused by every ODE evaluation
T_out_f   = interp1d(t_series, T_out_series,   fill_value="extrapolate")
Q_gains_f = interp1d(t_series, Q_gains_series, fill_value="extrapolate")
Q_rad_f   = interp1d(t_series, Q_rad_series,   fill_value="extrapolate")
Q_coil_f  = interp1d(t_series, Q_coil_series,  fill_value="extrapolate")

# --- Build and run the model ---
zone = Zone(C, R, Q_gains_f)
vav  = VAV(ctrl, Q_rad_f)
ahu  = AHU(Q_coil_f, T_sasp, foa_min=0.2, foa0=f_oa)
model = SingleZone(zone, vav, ahu, T_out_f)

res = model.simulate(t_series, T_in0)

t_hours  = res["t"] / 3600
T_in_sol = res["T_in"]
msa_sol  = res["msa"]
foa_sol  = res["foa"]

# --- Plot ---
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=[6, 8], sharex=True)

ax1.plot(t_hours, T_in_sol,    label="Indoor temp")
ax1.plot(t_hours, T_out_series, label="Outdoor temp", ls="--")
ax1.axhline(vav.T_set, color="k", ls=":", label="Setpoint")
ax1.set_ylabel("Temperature [°C]")
ax1.legend(frameon=False)

ax2.plot(t_hours, msa_sol)
ax2.set_ylabel("Supply air flow [L/s]")

ax3.step(t_hours, foa_sol, where="post")
ax3.set_xlabel("Time [h]")
ax3.set_ylabel("Outdoor air fraction [-]")

fig.tight_layout()
plt.show()
