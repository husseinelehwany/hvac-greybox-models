import os
import sys
import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

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
    rho    = 1.2     # kg/m³
    cp     = 1006.0  # J/(kg·K)
    T_ma   = foa * T_oa + (1 - foa) * T_ra
    T_sa   = T_ma + Q_coil / ( rho* cp * msa / 1000 )
    return T_sa, T_ma


def vav_heat(T_in, Q_rad, msa, T_sa):
    """Heat delivered by a VAV unit [W].

    Q_vav = srad * Q_rad  +  msa * cp_air * (T_sa - T_in)
      Q_rad  : reheat coil capacity [W]
      msa    : supply air mass flow rate [L/s]
      T_sa   : supply air temperature [°C]
      T_in   : current zone temperature [°C]
    """
    rho = 1.2 # kg/m3
    cp = 1006.0  # J/(kg·K)
    Q_vav = Q_rad + rho * cp * (msa/1000) * (T_sa - T_in)
    return Q_vav

def zone_rc_vav(t, T_in, C, R, t_series, T_out_series, Q_gains_series, Qrad_series, msa_series, f_oa, Q_coil_series):
    T_out   = interp1d(t_series, T_out_series,   fill_value="extrapolate")(t)
    # AHU .. assume 1 VAV per AHU
    Q_coil = interp1d(t_series, Q_coil_series,   fill_value="extrapolate")(t)
    msa   = interp1d(t_series, msa_series,   fill_value="extrapolate")(t)
    T_sa, T_ma = ahu_supply_temp(T_out, T_in, f_oa, Q_coil, msa) 
    # VAV
    Q_rad  = interp1d(t_series, Q_rad_series,  fill_value="extrapolate")(t)
    Q_hvac  = vav_heat(T_in, Q_rad, msa, T_sa)
    # zone 
    Q_gains = interp1d(t_series, Q_gains_series, fill_value="extrapolate")(t)
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
n = len(T_out_series)                    # 8760 hours
t_series = np.arange(0, n * 3600, 3600)  # 0 to 8759 h in seconds
Q_gains_series = np.array([500.0] * n)   # 500 W constant internal gains
# T_sa_series  = np.array([18]   * n) 

# --- Control actuators ---
f_oa = 0.2
Q_coil_series  = np.array([500]   * n) 
Q_rad_series  = np.array([500]   * n) 
msa_series = np.array([50]   * n) 

# --- Solve ---
sol = solve_ivp(
    fun=lambda t, y: zone_rc_vav(t, y, C, R, t_series, T_out_series, Q_gains_series, Q_rad_series, msa_series, f_oa, Q_coil_series),
    t_span=(t_series[0], t_series[-1]),
    y0=[T_in0],
    t_eval=t_series,
    method="RK45"
)

T_in_sol = sol.y[0]
t_hours  = sol.t / 3600

# --- Plot ---
plt.figure(figsize=[6, 3.5])
plt.plot(t_hours, T_in_sol,    label="Indoor temp")
plt.plot(t_hours, T_out_series, label="Outdoor temp", ls="--")
plt.xlabel("Time [h]")
plt.ylabel("Temperature [°C]")
plt.legend(frameon=False)
plt.tight_layout()
plt.show()
