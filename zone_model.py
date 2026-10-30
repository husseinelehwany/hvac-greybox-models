import os
import sys
import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

# --- Air properties ---
RHO_AIR = 1.2     # density [kg/m³]
CP_AIR  = 1006.0  # specific heat [J/(kg·K)]

def zone_rc(T_in, C, R, T_out, Q_hvac, Q_gains):
    dT_dt = (1/C) * ((T_out - T_in) / R + Q_hvac + Q_gains)
    return dT_dt

def economizer(T_oa, T_ra,T_ma, T_sasp):
    foa = 0.2
    if T_sasp > T_ma:
        foa = 0.2
    elif T_ra > T_sasp > T_oa:
        foa = np.clip((T_sasp - T_ra) / (T_oa - T_ra), 0.2, 1.0)
    elif T_ra > T_oa > T_sasp:
        foa = 1.0
    elif T_ma > T_sasp:
        foa = 0.2
    return foa

def ahu_supply_temp(T_oa, T_ra, foa, Q_coil, msa):
    """Calculate AHU supply air temperature [°C].

    Args:
        T_oa   : outdoor air temperature [°C]
        T_ra   : return air temperature [°C]  (≈ zone temperature)
        foa    : outdoor air fraction (0–1) - previous time step
        Q_coil : coil heat transfer [W], positive = heating, negative = cooling
        msa    : supply air volumetric flow rate [L/s]

    Returns:
        T_sa   : supply air temperature [°C]
        T_ma   : mixed air temperature [°C]
    """
    T_ma   = foa * T_oa + (1 - foa) * T_ra
    if msa > 0:
        T_sa   = T_ma + Q_coil / ( RHO_AIR * CP_AIR * msa / 1000 )
    else:
        T_sa = 18
    return T_sa, T_ma


def vav_heat(T_in, Q_rad, msa, T_sa):
    """Heat delivered by a VAV unit [W].

    Q_vav = srad * Q_rad  +  msa * cp_air * (T_sa - T_in)
      Q_rad  : reheat coil capacity [W]
      msa    : supply air mass flow rate [L/s]
      T_sa   : supply air temperature [°C]
      T_in   : current zone temperature [°C]
    """
    Q_vav = Q_rad + RHO_AIR * CP_AIR * (msa/1000) * (T_sa - T_in)
    return Q_vav

def p_flow(T_in, T_set, Kp, msa_min, msa_max, direction=1):
    """Proportional controller: indoor temperature -> supply air flow [L/s].

    direction = +1 : flow rises when T_in > T_set (cooling)
    direction = -1 : flow rises when T_in < T_set (heating)
    """
    e = direction * (T_in - T_set)
    return np.clip(msa_min + Kp * e, msa_min, msa_max)

def zone_rc_vav(t, T_in, C, R, T_out_f, Q_gains_f, Q_rad_f, f_oa, Q_coil_f, ctrl):
    T_out   = T_out_f(t)
    # AHU .. assume 1 VAV per AHU
    Q_coil = Q_coil_f(t)
    # P control on indoor temperature sets the supply air flow
    msa   = p_flow(T_in, **ctrl)
    T_sa, T_ma = ahu_supply_temp(T_out, T_in, f_oa, Q_coil, msa) 
    # VAV
    Q_rad  = Q_rad_f(t)
    Q_hvac  = vav_heat(T_in, Q_rad, msa, T_sa)
    # zone 
    Q_gains = Q_gains_f(t)
    dT_dt = zone_rc(T_in, C, R, T_out, Q_hvac, Q_gains)

    return dT_dt

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
# T_sa_series  = np.array([18]   * n) 

# --- Control actuators ---
f_oa = 0.2
Q_coil_series  = np.array([1200]   * n) 
Q_rad_series  = np.array([1000]   * n) 

# Proportional controller (direction=-1: more flow when zone is below setpoint, i.e. heating)
ctrl = dict(T_set=22.0, Kp=20.0, msa_min=10.0, msa_max=800, direction=-1)

# Interpolators, built once and reused by every ODE evaluation
T_out_f   = interp1d(t_series, T_out_series,   fill_value="extrapolate")
Q_gains_f = interp1d(t_series, Q_gains_series, fill_value="extrapolate")
Q_rad_f   = interp1d(t_series, Q_rad_series,   fill_value="extrapolate")
Q_coil_f  = interp1d(t_series, Q_coil_series,  fill_value="extrapolate")

# Economizer
T_sasp  = 18.0   # supply air temperature setpoint [°C]
foa_prev = f_oa   # initial outdoor air fraction

# --- Solve (one interval per time step; foa is held constant within each interval) ---
T_in = T_in0
T_in_hist = [T_in0]
foa_hist  = []

for k in range(n - 1):
    T_oa = T_out_series[k]

    # mixed air temperature using the PREVIOUS foa
    T_ma = foa_prev * T_oa + (1 - foa_prev) * T_in

    # CURRENT foa from the economizer, held for this interval
    foa = economizer(T_oa, T_in, T_ma, T_sasp)

    sol = solve_ivp(
        fun=lambda t, y: zone_rc_vav(t, y, C, R, T_out_f, Q_gains_f, Q_rad_f, foa, Q_coil_f, ctrl),
        t_span=(t_series[k], t_series[k + 1]),
        y0=[T_in],
        method="RK45",
        max_step=300
    )
    T_in = sol.y[0, -1]

    T_in_hist.append(T_in)
    foa_hist.append(foa)
    foa_prev = foa

foa_hist.append(foa_prev)  # pad so all series have n points

T_in_sol = np.array(T_in_hist)
foa_sol  = np.array(foa_hist)
msa_sol  = p_flow(T_in_sol, **ctrl)
t_hours  = t_series / 3600

# --- Plot ---
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=[6, 8], sharex=True)

ax1.plot(t_hours, T_in_sol,    label="Indoor temp")
ax1.plot(t_hours, T_out_series, label="Outdoor temp", ls="--")
ax1.axhline(ctrl["T_set"], color="k", ls=":", label="Setpoint")
ax1.set_ylabel("Temperature [°C]")
ax1.legend(frameon=False)

ax2.plot(t_hours, msa_sol)
ax2.set_ylabel("Supply air flow [L/s]")

ax3.step(t_hours, foa_sol, where="post")
ax3.set_xlabel("Time [h]")
ax3.set_ylabel("Outdoor air fraction [-]")

fig.tight_layout()
plt.show()
