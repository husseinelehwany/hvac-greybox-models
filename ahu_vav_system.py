import numpy as np
from scipy.integrate import solve_ivp


class ZoneModel:
    """Zone + VAV + AHU system, simulated with one control step per time step.

    Args:
        zone    : Zone instance
        vav     : VAV instance
        ahu     : AHU instance
        T_out_f : interpolator t [s] -> outdoor air temperature [°C]
    """
    def __init__(self, zone, vav, ahu, T_out_f):
        self.zone = zone
        self.vav = vav
        self.ahu = ahu
        self.T_out_f = T_out_f

    def rhs(self, t, T_in, foa):
        """Zone temperature derivative [K/s] for outdoor air fraction foa."""
        T_out  = self.T_out_f(t)
        # P control on indoor temperature sets the supply air flow
        msa    = self.vav.flow(T_in)
        # AHU .. assume 1 VAV per AHU
        T_sa, T_ma = self.ahu.supply_temp(t, T_out, T_in, foa, msa)
        Q_hvac = self.vav.heat(t, T_in, msa, T_sa)
        return self.zone.dTdt(t, T_in, T_out, Q_hvac)

    def simulate(self, t_series, T_in0, method="RK45", max_step=300):
        """Simulate over t_series [s]; foa is held constant within each interval.

        Returns:
            dict with arrays t [s], T_in [°C], msa [L/s], foa [-], all of length len(t_series)
        """
        n = len(t_series)
        T_in = T_in0
        T_in_hist = [T_in0]
        foa_hist  = []

        for k in range(n - 1):
            # CURRENT foa from the AHU economizer (using the previous foa), held for this interval
            foa = self.ahu.step(self.T_out_f(t_series[k]), T_in)

            sol = solve_ivp(
                fun=lambda t, y: self.rhs(t, y, foa),
                t_span=(t_series[k], t_series[k + 1]),
                y0=[T_in],
                method=method,
                max_step=max_step
            )
            T_in = sol.y[0, -1]

            T_in_hist.append(T_in)
            foa_hist.append(foa)

        foa_hist.append(self.ahu.foa_prev)  # pad so all series have n points

        T_in_sol = np.array(T_in_hist)
        return dict(
            t=np.asarray(t_series),
            T_in=T_in_sol,
            msa=self.vav.flow(T_in_sol),
            foa=np.array(foa_hist),
        )
