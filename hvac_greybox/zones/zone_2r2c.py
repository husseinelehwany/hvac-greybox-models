class Zone2R2C:
    """Thermal zone with an air node and an internal thermal mass node (2R2C model).

        T_out --[R_out]-- T_in --[R_m]-- T_m
                           |              |
                          C_in           C_m

        C_in · dT_in/dt = (T_out − T_in)/R_out + (T_m − T_in)/R_m + Q_hvac + Q_solar + Q_gains
        C_m  · dT_m/dt  = (T_in − T_m)/R_m

    The air node is coupled to outdoors (walls and windows lumped in R_out). The mass
    (floors, furniture, inner wall layers) exchanges heat only with the air. HVAC, solar
    and internal gains all enter the air node.

    Args:
        C_in      : thermal capacitance of the air node [J/K]
        C_m       : thermal capacitance of the mass node [J/K]
        R_out     : thermal resistance between outdoors and indoor air [K/W]
        R_m       : thermal resistance between indoor air and the mass [K/W]
        Q_solar_f : interpolator t [s] -> solar heat gain [W]
        Q_gains_f : interpolator t [s] -> internal gains [W]
    """
    def __init__(self, C_in, C_m, R_out, R_m, Q_solar_f, Q_gains_f):
        self.C_in = C_in
        self.C_m = C_m
        self.R_out = R_out
        self.R_m = R_m
        self.Q_solar_f = Q_solar_f
        self.Q_gains_f = Q_gains_f

    def dTdt(self, t, T_in, T_m, T_out, Q_hvac):
        """Derivatives [K/s] of the air and mass temperatures for the given HVAC heat input [W].

        Returns:
            (dT_in/dt, dT_m/dt)
        """
        Q_mass = (T_m - T_in) / self.R_m   # heat from the mass to the air [W]
        dT_in = (1 / self.C_in) * ((T_out - T_in) / self.R_out + Q_mass + Q_hvac
                                   + self.Q_solar_f(t) + self.Q_gains_f(t))
        dT_m = (1 / self.C_m) * (-Q_mass)
        return dT_in, dT_m
