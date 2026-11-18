import numpy as np
from controller import Controller

class PController(Controller):
    """Proportional controller with output limits.

        y = clip(out_min + Kp * e, out_min, out_max),   e = direction * (x - setpoint)

    Args:
        setpoint  : setpoint, in the units of x
        Kp        : proportional gain [output units per unit of x]
        out_min   : minimum output, also the output at zero error
        out_max   : maximum output
        direction : +1 : output rises when x > setpoint (e.g. cooling)
                    -1 : output rises when x < setpoint (e.g. heating)
    """
    def __init__(self, setpoint, Kp, out_min, out_max, direction=1):
        super().__init__(setpoint)
        self.Kp = Kp
        self.out_min = out_min
        self.out_max = out_max
        self.direction = direction

    def output(self, x):
        e = self.direction * (x - self.setpoint)
        return np.clip(self.out_min + self.Kp * e, self.out_min, self.out_max)
