import numpy as np
from hvac_greybox.controllers.controller import Controller

class DeadbandPController(Controller):
    """Proportional heating/cooling sequence with a deadband around the setpoint.

    Cooling acts above sp_cool = setpoint + deadband/2 and heating below
    sp_heat = setpoint - deadband/2. Inside the deadband both outputs are 0.

        y_cool = clip(Kp_cool * (x - sp_cool), 0, 1)
        y_heat = clip(Kp_heat * (sp_heat - x), 0, 1)

    The outputs are fractions (0-1) that the equipment maps to its own range,
    e.g. for a VAV box with reheat:
        flow   = msa_min + y_cool * (msa_max - msa_min)
        reheat = y_heat * Q_rad_rated

    Args:
        setpoint : centre of the deadband, in the units of x
        deadband : width of the deadband (>= 0), in the units of x
        Kp_cool  : cooling gain [1/unit of x]; full cooling 1/Kp_cool above sp_cool
        Kp_heat  : heating gain [1/unit of x]; full heating 1/Kp_heat below sp_heat
    """
    def __init__(self, setpoint, deadband, Kp_cool, Kp_heat):
        if deadband < 0:
            raise ValueError("deadband must be >= 0")
        super().__init__(setpoint)
        self.deadband = deadband
        self.Kp_cool = Kp_cool
        self.Kp_heat = Kp_heat

    @property
    def sp_cool(self):
        return self.setpoint + self.deadband / 2

    @property
    def sp_heat(self):
        return self.setpoint - self.deadband / 2

    def output(self, x):
        """Return (y_cool, y_heat), each between 0 and 1."""
        y_cool = np.clip(self.Kp_cool * (x - self.sp_cool), 0.0, 1.0)
        y_heat = np.clip(self.Kp_heat * (self.sp_heat - x), 0.0, 1.0)
        return y_cool, y_heat
