"""Grey-box HVAC models: RC zone models, VAV boxes, an AHU with economizer, controllers
and EPW weather data.

Subpackages:
    zones        Zone (1R1C), Zone2R2C
    equipment    AHU, VAV
    controllers  Controller, PController, DeadbandPController
    systems      AHUVAVSingleZone, AHUVAVTwoZones
    plotting     plot_ahu_vav, plot_foa_vs_toa
    gui          Streamlit schematics (needs streamlit; not imported here)

Example:
    from hvac_greybox.zones import Zone2R2C
    from hvac_greybox.systems import AHUVAVTwoZones
"""
from pathlib import Path

__version__ = "0.1.0"

# Project folders, built from this file's location so they work from any working directory
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
