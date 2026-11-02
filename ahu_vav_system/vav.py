import numpy as np
from constants import RHO_AIR, CP_AIR


class VAV:
    """VAV box with reheat coil and a proportional flow controller.

    Args:
        ctrl    : P-controller settings (T_set, Kp, msa_min, msa_max, direction)
                  direction = +1 : flow rises when T_in > T_set (cooling)
                  direction = -1 : flow rises when T_in < T_set (heating)
        Q_rad_f : interpolator t [s] -> reheat coil heat [W]
    """
    def __init__(self, ctrl, Q_rad_f):
        self.ctrl = ctrl
        self.Q_rad_f = Q_rad_f

    @property
    def T_set(self):
        return self.ctrl["T_set"]

    def flow(self, T_in):
        """Supply air flow requested by the zone temperature controller [L/s]."""
        c = self.ctrl
        e = c.get("direction", 1) * (T_in - c["T_set"])
        msa = np.clip(c["msa_min"] + c["Kp"] * e, c["msa_min"], c["msa_max"])
        return msa

    def heat(self, t, T_in, msa, T_sa):
        """Heat delivered to the zone [W].

        Q_vav = Q_rad + rho * cp * msa * (T_sa - T_in)
          msa  : supply air volumetric flow rate [L/s]
          T_sa : supply air temperature [°C]
          T_in : current zone temperature [°C]
        """
        Q_vav = self.Q_rad_f(t) + RHO_AIR * CP_AIR * (msa / 1000) * (T_sa - T_in)
        return Q_vav
