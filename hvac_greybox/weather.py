from datetime import datetime
import numpy as np


class Weather:
    """Hourly weather from an EPW file (8760 hours, no leap day).

    Args:
        epw_path : path to the EPW file

    Index 0 is Jan 1 00:00-01:00 (EPW hour 1). The year of any datetime is
    ignored, since an EPW file is a typical year. Minutes and seconds are
    dropped (the hour is floored), and Feb 29 is rejected.
    """
    HOURS_PER_YEAR = 8760
    EPW_HEADER_LINES = 8
    EPW_DRY_BULB_COLUMN = 6   # dry bulb temperature [°C]
    EPW_GHI = 13  # Global Horizontal Irradiance
    EPW_DNI = 14  # Direct Normal Irradiance
    EPW_DHI = 15  # Diffuse Horizontal Irradiance

    def __init__(self, epw_path):
        self.epw_path = epw_path
        with open(epw_path, "r") as f:
            lines = f.readlines()[self.EPW_HEADER_LINES:]
        self.T_dry_bulb = np.array(
            [float(line.split(",")[self.EPW_DRY_BULB_COLUMN]) for line in lines if line.strip()]
        )
        self.GHI = np.array(
            [float(line.split(",")[self.EPW_GHI]) for line in lines if line.strip()]
        )
        self.DNI = np.array(
                    [float(line.split(",")[self.EPW_DNI]) for line in lines if line.strip()]
                )
        self.DHI = np.array(
                            [float(line.split(",")[self.EPW_DHI]) for line in lines if line.strip()]
                        )
        if len(self.T_dry_bulb) != self.HOURS_PER_YEAR:
            raise ValueError(f"expected {self.HOURS_PER_YEAR} hourly rows, got {len(self.T_dry_bulb)}")

    @staticmethod
    def hour_of_year(dt):
        """Index (0-8759) of the hour containing dt."""
        if dt.month == 2 and dt.day == 29:
            raise ValueError("Feb 29 is not in the 8760-hour EPW year")
        day_of_year = datetime(2001, dt.month, dt.day).timetuple().tm_yday  # 2001: non-leap
        return (day_of_year - 1) * 24 + dt.hour

    def hour_indices(self, start, end):
        """Indices of the hourly samples from start to end, both inclusive."""
        i_start, i_end = self.hour_of_year(start), self.hour_of_year(end)
        if i_end < i_start:
            raise ValueError("end is before start (periods that wrap the year are not supported)")
        return np.arange(i_start, i_end + 1)

    def temperature_between(self, start, end):
        """Outdoor dry bulb temperatures [°C] for each hour from start to end, both inclusive."""
        idx = self.hour_indices(start, end)
        return self.T_dry_bulb[idx]

    def get_solar_irradiance(self, start, end):
        """DNI + DHI [W/m²] for each hour from start to end, both inclusive."""
        idx = self.hour_indices(start, end)
        return self.DNI[idx] + self.DHI[idx]

    def get_ghi(self, start, end):
        """Global horizontal irradiance [W/m²] for each hour from start to end, both inclusive."""
        idx = self.hour_indices(start, end)
        return self.GHI[idx]

