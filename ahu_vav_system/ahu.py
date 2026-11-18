import numpy as np
from constants import RHO_AIR, CP_AIR


class AHU:
    """Air handling unit: mixing box with economizer and a heating/cooling coil.

    Args:
        Q_coil_rated : rated coil heat transfer [W]; the coil output is limited to
                       +/- this value (positive = heating, negative = cooling)
        T_sasp       : supply air temperature setpoint [°C]
        Kp_coil      : proportional gain of the coil controller [W/K]
        foa_min      : minimum outdoor air fraction (0-1)
        foa0         : initial outdoor air fraction (0-1)

    The economizer decision uses the mixed air temperature from the previous
    outdoor air fraction, so the AHU keeps `foa_prev` as state (see `step`).
    """
    def __init__(self, Q_coil_rated, T_sasp, Kp_coil=1000.0, foa_min=0.2, foa0=0.2):
        self.Q_coil_rated = Q_coil_rated
        self.T_sasp = T_sasp
        self.Kp_coil = Kp_coil
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
        econ_ok = True if T_oa < (T_ra -0.5) else False
        if T_ma < T_sasp - 0.5:  # heating
            foa = foa_min
        elif econ_ok:
            if T_ra > T_sasp > T_oa:
             foa = np.clip((T_sasp - T_ra) / (T_oa - T_ra), foa_min, 1.0)
            elif T_ra > T_oa > T_sasp:
                foa = 1.0
        else:  # high limit shutoff
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

    def coil_heat(self, T_ma, msa):
        """Coil heat transfer [W] from a proportional controller on the supply air temperature.

        The controller is Q = Kp_coil * (T_sasp - T_sa), clipped to +/- Q_coil_rated.
        Since T_sa = T_ma + Q / (rho * cp * msa) itself depends on Q, the unclipped
        loop is solved in closed form (no time lag, stable for any gain):

            Q = Kp_coil * (T_sasp - T_ma) / (1 + Kp_coil / (rho * cp * msa))

        Args:
            T_ma : mixed air temperature [°C]
            msa  : supply air volumetric flow rate [L/s]
        """
        m_cp = RHO_AIR * CP_AIR * msa / 1000   # air heat capacity rate [W/K]
        Q = self.Kp_coil * (self.T_sasp - T_ma) / (1 + self.Kp_coil / m_cp)
        return np.clip(Q, -self.Q_coil_rated, self.Q_coil_rated)

    def ideal_loads(self, T_ma, msa):
        """Ideal coil heat transfer [W] that brings the mixed air exactly to T_sasp.

        Q_ideal = rho * cp * msa * (T_sasp - T_ma), clipped to +/- Q_coil_rated
        (positive = heating, negative = cooling).

        Args:
            T_ma : mixed air temperature [°C]
            msa  : supply air volumetric flow rate [L/s]
        """
        m_cp = RHO_AIR * CP_AIR * msa / 1000   # air heat capacity rate [W/K]
        Q_ideal = m_cp * (self.T_sasp - T_ma)
        Q_clip = np.clip(Q_ideal, -self.Q_coil_rated, self.Q_coil_rated)
        return Q_clip

    def supply_temp(self, T_oa, T_ra, foa, msa):
        """Supply air temperature [°C] and mixed air temperature [°C].

        Args:
            T_oa  : outdoor air temperature [°C]
            T_ra  : return air temperature [°C]  (≈ zone temperature)
            foa   : outdoor air fraction (0-1) held over the current step
            msa   : supply air volumetric flow rate [L/s]
        """
        T_ma = self.mixed_air_temp(T_oa, T_ra, foa)
        if msa > 0:
            T_sa = T_ma + self.coil_heat(T_ma, msa) / (RHO_AIR * CP_AIR * msa / 1000)
        else:
            T_sa = self.T_sasp
        return T_sa, T_ma
