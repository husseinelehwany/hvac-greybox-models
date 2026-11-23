import numpy as np
from scipy.linalg import expm

from hvac_greybox.constants import RHO_AIR, CP_AIR


class AHUVAVTwoZones:
    """Two 2R2C zones (a and b), each with its own VAV, served by one AHU.

        outdoor air --> AHU (economizer + coil) --T_sa--> VAV a --> zone a --+
                         ^                         \\--> VAV b --> zone b --+
                         +------------- return air (flow-weighted mix) -----+

    Airflow coupling:
      * each VAV sets its own flow from its own zone temperature (msa_a, msa_b)
      * the AHU supplies the total flow msa = msa_a + msa_b at one supply temperature T_sa
      * the return air is the flow-weighted mix of the two zone temperatures,
        T_ra = (msa_a T_in_a + msa_b T_in_b) / msa, and feeds the economizer and mixing box

    The zones are thermally independent (no shared wall); they interact only through the AHU.

    Each step, the AHU and VAVs are evaluated from the state at the start of the step and
    held (zero-order hold). With those held, each zone is linear,

        C_in dT_in/dt = (T_out - T_in)/R_out + (T_m - T_in)/R_m + G_sa (T_sa - T_in) + Q_air
        C_m  dT_m/dt  = (T_in - T_m)/R_m

    with G_sa = rho * cp * msa of that zone's VAV and Q_air = baseboard + solar + internal
    gains, and it is advanced exactly over the step with the matrix exponential.

    Args:
        zone_a, zone_b : Zone2R2C instances
        vav_a, vav_b   : VAV instances serving zone a and zone b
        ahu            : AHU instance serving both VAVs
        T_out_f        : interpolator t [s] -> outdoor air temperature [°C]
    """
    def __init__(self, zone_a, zone_b, vav_a, vav_b, ahu, T_out_f):
        self.zone_a = zone_a
        self.zone_b = zone_b
        self.vav_a = vav_a
        self.vav_b = vav_b
        self.ahu = ahu
        self.T_out_f = T_out_f

    @staticmethod
    def discretize(zone, msa, dt):
        """Discrete matrices (Ad, Bd) of one zone for x_{k+1} = Ad x_k + Bd u_k over dt [s].

        x = [T_in, T_m], u = [T_out, T_sa, Q_air]; msa is that zone's supply air flow [L/s]
        held over the step. Both matrices come from one matrix exponential of
        [[A, B], [0, 0]] * dt.
        """
        z = zone
        G_sa = RHO_AIR * CP_AIR * msa / 1000   # supply air heat capacity rate [W/K]
        M = np.zeros((5, 5))
        M[:2, :2] = [
            [-(1 / z.R_out + 1 / z.R_m + G_sa) / z.C_in, 1 / (z.R_m * z.C_in)],
            [1 / (z.R_m * z.C_m),                        -1 / (z.R_m * z.C_m)],
        ]
        M[0, 2:] = [1 / (z.R_out * z.C_in), G_sa / z.C_in, 1 / z.C_in]
        E = expm(M * dt)
        return E[:2, :2], E[:2, 2:]

    @staticmethod
    def return_air_temp(T_in_a, T_in_b, msa_a, msa_b):
        """Return air temperature [°C]: flow-weighted mix of the zone temperatures."""
        msa = msa_a + msa_b
        if msa <= 0:
            return 0.5 * (T_in_a + T_in_b)
        return (msa_a * T_in_a + msa_b * T_in_b) / msa

    def simulate(self, t_series, T_in0_a, T_in0_b=None):
        """Simulate over t_series [s] (steps may vary in length).

        Args:
            t_series : sample times [s]
            T_in0_a  : initial temperature of zone a [°C] (air and mass)
            T_in0_b  : initial temperature of zone b [°C] (air and mass; default: T_in0_a)

        Returns:
            dict of arrays, all of length len(t_series):
              t [s]
              per zone (suffix _a, _b): T_in, T_m [°C], msa [L/s], Q_rad [W] (baseboard),
                                         Q_vav [W] (heat delivered to the zone by the VAV)
              AHU: msa [L/s] (total), T_ra [°C] (return air), foa [-], T_sa [°C],
                   Q_coil [W]
            The HVAC values at each sample are the ones held over the following step.
        """
        t_series = np.asarray(t_series, dtype=float)
        n = len(t_series)
        if T_in0_b is None:
            T_in0_b = T_in0_a
        zones = {"a": (self.zone_a, self.vav_a), "b": (self.zone_b, self.vav_b)}
        x = {"a": np.array([T_in0_a, T_in0_a], dtype=float),
             "b": np.array([T_in0_b, T_in0_b], dtype=float)}

        zone_keys = ("T_in", "T_m", "msa", "Q_rad", "Q_vav")
        ahu_keys = ("msa", "T_ra", "foa", "T_sa", "Q_coil")
        res = {f"{key}_{z}": np.empty(n) for key in zone_keys for z in zones}
        res.update({key: np.empty(n) for key in ahu_keys})

        for k in range(n):
            t = t_series[k]
            last = k == n - 1
            T_out = float(self.T_out_f(t))
            T_in = {z: x[z][0] for z in zones}

            # VAVs: each sets its flow from its own zone temperature
            msa = {z: float(vav.flow(T_in[z])) for z, (_, vav) in zones.items()}
            msa_tot = msa["a"] + msa["b"]
            T_ra = self.return_air_temp(T_in["a"], T_in["b"], msa["a"], msa["b"])

            # AHU: economizer on the mixed return air, coil on the total flow.
            # CURRENT foa (using the previous foa) is held for this step; at the last
            # sample no step follows, so report the held value
            foa = self.ahu.foa_prev if last else self.ahu.step(T_out, T_ra)
            T_sa, T_ma = self.ahu.supply_temp(T_out, T_ra, foa, msa_tot)
            T_sa = float(T_sa)
            Q_coil = float(self.ahu.coil_heat(T_ma, msa_tot)) if msa_tot > 0 else 0.0

            for key, value in zip(ahu_keys, (msa_tot, T_ra, foa, T_sa, Q_coil)):
                res[key][k] = value

            for z, (zone, vav) in zones.items():
                Q_rad = float(vav.baseboard_heater(T_in[z]))
                res[f"T_in_{z}"][k], res[f"T_m_{z}"][k] = x[z]
                res[f"msa_{z}"][k] = msa[z]
                res[f"Q_rad_{z}"][k] = Q_rad
                res[f"Q_vav_{z}"][k] = float(vav.heat(T_in[z], msa[z], T_sa))

                if not last:
                    Q_air = Q_rad + float(zone.Q_solar_f(t)) + float(zone.Q_gains_f(t))
                    Ad, Bd = self.discretize(zone, msa[z], t_series[k + 1] - t)
                    x[z] = Ad @ x[z] + Bd @ np.array([T_out, T_sa, Q_air])

        res["t"] = t_series
        return res
