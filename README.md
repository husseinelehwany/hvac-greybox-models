# hvac-greybox-models
Greybox models for building and HVAC systems

## Overview

A simple grey-box (lumped RC) simulation of a single thermal zone served by a VAV box, which is in turn fed by an air handling unit (AHU) with an economizer. The model is driven by hourly outdoor temperature from an EPW weather file (Ottawa, CWEC) and shows how the zone temperature, supply air flow and outdoor air fraction evolve under proportional control.

## Model

**Zone** (first-order RC model):

```
C · dT_in/dt = (T_out − T_in) / R + Q_hvac + Q_gains
```

**VAV box** with reheat coil:

```
Q_hvac = Q_rad + ρ · cp · V̇_sa · (T_sa − T_in)
V̇_sa   = clip(V̇_min + Kp · e, V̇_min, V̇_max),   e = direction · (T_in − T_set)
```

The supply air flow V̇_sa [L/s] is set by a proportional controller on the indoor temperature. `direction = −1` gives more flow when the zone is below setpoint (heating), `+1` when above (cooling).

**AHU** with economizer and coil:

```
T_ma = foa · T_oa + (1 − foa) · T_ra
T_sa = T_ma + Q_coil / (ρ · cp · V̇_sa)
```

The economizer picks the outdoor air fraction `foa` (between a minimum and 1.0) from the outdoor, return and mixed air temperatures and the supply air temperature setpoint. The mixed air temperature used for that decision is based on the previous time step's `foa`, so the algebraic loop is broken. `foa` is then held constant over each time step.

## Simulation approach

Time is stepped hourly. For each step the AHU chooses `foa`, then `scipy.integrate.solve_ivp` (RK45) integrates the zone temperature over that interval, with the weather, internal gains, reheat and coil heat interpolated in time. Results are the indoor temperature, supply air flow and outdoor air fraction over time.

## Project structure

| File | Contents |
|---|---|
| `main.py` | Inputs (weather, parameters, schedules), builds the components, runs the simulation and plots the results |
| `zone.py` | `Zone`: RC zone model |
| `vav.py` | `VAV`: VAV box with reheat coil and proportional flow controller |
| `ahu.py` | `AHU`: mixing box, economizer and coil |
| `ahu_vav_system.py` | Class that couples zone, VAV and AHU and runs the time-stepping loop |
| `constants.py` | Air density and specific heat |
| `zone_model.py` | Earlier single-file version of the model (functions plus a script) |
| `input_files/` | EPW weather file |

## Requirements

Python 3 with `numpy`, `scipy` and `matplotlib`.

## Usage

Run from the repository root so the relative path to `input_files/` resolves:

```
python main.py
```

Parameters (zone `C` and `R`, setpoint, controller gain, flow limits, coil and reheat power, supply air setpoint, simulated duration) are set at the top of `main.py`.

## Units

Temperatures in °C, heat flows in W, thermal capacitance in J/K, thermal resistance in K/W, time in s, and supply air flow in L/s (volumetric).
