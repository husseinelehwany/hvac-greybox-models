import numpy as np


class Controller:
    """Base class for controllers: maps a measurement x to a control output with `output(x)`.

    Args:
        setpoint : setpoint, in the units of x
    """
    def __init__(self, setpoint):
        self.setpoint = setpoint

    def output(self, x):
        raise NotImplementedError
