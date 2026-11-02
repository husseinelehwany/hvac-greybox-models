import numpy as np
from constants import RHO_AIR, CP_AIR


class AHU:
    """Air handling unit: mixing box with economizer and a heating/cooling coil.

    Args:
        Q_coil_f : interpolator t [s] -> coil heat transfer [W], positive = heating, negative = cooling
        T_sasp   : supply air temperature setpoint [°C]
        foa_min  : minimum outdoor air fraction (0-1)
        foa0     : initial outdoor air fraction (0-1)

    The economizer decision uses the mixed air temperature from the previous
    outdoor air fraction, so the AHU keeps `foa_prev` as state (see `step`).
    """
    def __init__(self, Q_coil_f, T_sasp, foa_min=0.2, foa0=0.2):
        self.Q_coil_f = Q_coil_f
        self.T_sasp = T_sasp
        self.foa_min = foa_min
        self.foa_prev = foa0

    @staticmethod
    def mixed_air_temp(T_oa, T_ra, foa):
        """Mixed air temperature [°C] for outdoor air fraction foa."""
        return foa * T_oa + (1 - foa) * T_ra

    def economizer(self, T_oa, T_ra, T_ma):
        """Outdoor air fraction (0-1) chosen from outdoor, return and mixed air temperatures [°C]."""
        T_sasp, foa_min = self.T_sasp, self.foa_min
        foa = foa_min
        if T_sasp > T_ma:
            foa = foa_min
        elif T_ra > T_sasp > T_oa:
            foa = np.clip((T_sasp - T_ra) / (T_oa - T_ra), foa_min, 1.0)
        elif T_ra > T_oa > T_sasp:
            foa = 1.0
        elif T_ma > T_sasp:
            foa = foa_min
        return foa

    def step(self, T_oa, T_ra):
        """Advance one control step and return the new outdoor air fraction.

        T_ma is computed from the PREVIOUS foa, the economizer then picks the
        CURRENT foa, which becomes the previous foa for the next step.
        """
        T_ma = self.mixed_air_temp(T_oa, T_ra, self.foa_prev)
        foa = self.economizer(T_oa, T_ra, T_ma)
        self.foa_prev = foa
        return foa

    def supply_temp(self, t, T_oa, T_ra, foa, msa):
        """Supply air temperature [°C] and mixed air temperature [°C].

        Args:
            t     : time [s]
            T_oa  : outdoor air temperature [°C]
            T_ra  : return air temperature [°C]  (≈ zone temperature)
            foa   : outdoor air fraction (0-1) held over the current step
            msa   : supply air volumetric flow rate [L/s]
        """
        T_ma = self.mixed_air_temp(T_oa, T_ra, foa)
        if msa > 0:
            T_sa = T_ma + self.Q_coil_f(t) / (RHO_AIR * CP_AIR * msa / 1000)
        else:
            T_sa = self.T_sasp
        return T_sa, T_ma
