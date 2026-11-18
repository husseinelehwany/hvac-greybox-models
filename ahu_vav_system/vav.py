from constants import RHO_AIR, CP_AIR


class VAV:
    """VAV box with baseboard heater, controlled by a deadband P controller on the zone temperature.

    Above the deadband the cooling output opens the damper from msa_min to msa_max.
    Below the deadband the flow stays at msa_min and the heating output ramps the baseboard heater.

    Args:
        controller  : DeadbandPController on the zone temperature, output(T_in) -> (y_cool, y_heat)
        msa_min     : minimum supply air flow [L/s]
        msa_max     : maximum supply air flow [L/s]
        Q_rad_rated : rated baseboard heat [W]
    """
    def __init__(self, controller, msa_min, msa_max, Q_rad_rated):
        self.controller = controller
        self.msa_min = msa_min
        self.msa_max = msa_max
        self.Q_rad_rated = Q_rad_rated

    @property
    def T_set(self):
        return self.controller.setpoint

    def flow(self, T_in):
        """Supply air flow [L/s] from the cooling output of the controller."""
        y_cool, _ = self.controller.output(T_in)
        return self.msa_min + y_cool * (self.msa_max - self.msa_min)

    def baseboard_heater(self, T_in):
        """baseboard heat [W] from the heating output of the controller."""
        _, y_heat = self.controller.output(T_in)
        return y_heat * self.Q_rad_rated

    def heat(self, T_in, msa, T_sa):
        """Heat delivered to the zone [W].

        Q_vav = Q_rad + rho * cp * msa * (T_sa - T_in)
          msa  : supply air volumetric flow rate [L/s]
          T_sa : supply air temperature [°C]
          T_in : current zone temperature [°C]
        """
        Q_vav = self.baseboard_heater(T_in) + RHO_AIR * CP_AIR * (msa / 1000) * (T_sa - T_in)
        return Q_vav
