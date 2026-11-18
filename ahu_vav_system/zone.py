class Zone:
    """Single thermal zone (RC model).

    Args:
        C         : thermal capacitance [J/K]
        R         : thermal resistance to outdoors [K/W]
        Q_solar_f : interpolator t [s] -> solar heat gain [W]
        Q_gains_f : interpolator t [s] -> internal gains [W]
    """
    def __init__(self, C, R, Q_solar_f, Q_gains_f):
        self.C = C
        self.R = R
        self.Q_solar_f = Q_solar_f
        self.Q_gains_f = Q_gains_f

    def dTdt(self, t, T_in, T_out, Q_hvac):
        """Zone temperature derivative [K/s] for the given HVAC heat input [W]."""
        return (1 / self.C) * ((T_out - T_in) / self.R + Q_hvac + self.Q_solar_f(t) + self.Q_gains_f(t))
