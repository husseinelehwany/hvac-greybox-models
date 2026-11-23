import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def plot_ahu_vav(times, res, T_out_series, sp_heat, sp_cool):
    """Time series of temperatures, supply air flow, outdoor air fraction and heat flows."""
    T_in_sol = res["T_in"]
    msa_sol  = res["msa"]
    foa_sol  = res["foa"]

    fig, ax = plt.subplots(4, 1, figsize=[6, 10], sharex=True)

    ax[0].plot(times, T_in_sol,    label="Indoor temp")
    ax[0].plot(times, T_out_series, label="Outdoor temp", ls="--")
    ax[0].plot(times, res["T_sa"],  label="Supply air temp")
    ax[0].axhspan(sp_heat, sp_cool, color="grey", alpha=0.2, label="Deadband")
    ax[0].set_ylabel("Temperature [°C]")
    ax[0].legend(frameon=False)

    ax[1].plot(times, msa_sol)
    ax[1].set_ylabel("Supply air flow [L/s]")

    ax[2].step(times, foa_sol, where="post")
    ax[2].set_ylabel("Outdoor air fraction [-]")

    ax[3].plot(times, res["Q_coil"], label="AHU coil")
    ax[3].plot(times, res["Q_rad"],  label="VAV reheat")
    ax[3].plot(times, res["Q_vav"],  label="VAV to zone")
    ax[3].axhline(0, color="k", lw=0.5)
    ax[3].set_xlabel("Time")
    ax[3].xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    ax[3].set_ylabel("Heat [W]")
    ax[3].legend(frameon=False)

    fig.tight_layout()
    return fig


def plot_ahu_vav_two_zones(times, res, T_out_series, sp_a, sp_b):
    """Time series of the two-zone system: zone a and zone b on the same axes, AHU values once.

    Args:
        times        : datetimes of the samples
        res          : results of AHUVAVTwoZones.simulate (keys with _a / _b suffix)
        T_out_series : outdoor air temperature at the samples [°C]
        sp_a, sp_b   : (heating, cooling) setpoints of zone a and zone b [°C]
    """
    colors = {"a": "C0", "b": "C1"}
    fig, ax = plt.subplots(4, 1, figsize=[6, 11], sharex=True)

    for z, (sp_heat, sp_cool) in (("a", sp_a), ("b", sp_b)):
        ax[0].plot(times, res[f"T_in_{z}"], color=colors[z], label=f"Zone {z}")
        ax[0].axhspan(sp_heat, sp_cool, color=colors[z], alpha=0.12, label=f"Deadband {z}")
    ax[0].plot(times, T_out_series, color="grey", ls="--", label="Outdoor")
    ax[0].plot(times, res["T_sa"], color="C2", lw=1, label="Supply air")
    ax[0].set_ylabel("Temperature [°C]")
    ax[0].legend(frameon=False, fontsize=8, ncol=2)

    for z in ("a", "b"):
        ax[1].plot(times, res[f"msa_{z}"], color=colors[z], label=f"VAV {z}")
    ax[1].plot(times, res["msa"], color="k", lw=1, label="AHU total")
    ax[1].set_ylabel("Supply air flow [L/s]")
    ax[1].legend(frameon=False, fontsize=8)

    ax[2].step(times, res["foa"], where="post")
    ax[2].set_ylabel("Outdoor air fraction [-]")

    ax[3].plot(times, res["Q_coil"], color="k", lw=1, label="AHU coil")
    for z in ("a", "b"):
        ax[3].plot(times, res[f"Q_rad_{z}"], color=colors[z], label=f"Baseboard {z}")
        ax[3].plot(times, res[f"Q_vav_{z}"], color=colors[z], ls="--", label=f"VAV {z} to zone")
    ax[3].axhline(0, color="k", lw=0.5)
    ax[3].set_xlabel("Time")
    ax[3].xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    ax[3].set_ylabel("Heat [W]")
    ax[3].legend(frameon=False, fontsize=8, ncol=2)

    fig.tight_layout()
    return fig


def plot_foa_vs_toa(res, T_out_series):
    """Scatter of the outdoor air fraction against the outdoor air temperature.

    Points are coloured by the indoor (return air) temperature, since the
    economizer decision depends on the outdoor vs return air temperature.
    """
    fig, ax = plt.subplots(figsize=[6, 4.5])
    sc = ax.scatter(T_out_series, res["foa"], c=res["T_in"], s=10, cmap="viridis")
    fig.colorbar(sc, ax=ax, label="Return air (indoor) temp [°C]")
    ax.set_xlabel("Outdoor air temperature [°C]")
    ax.set_ylabel("Outdoor air fraction [-]")
    ax.set_ylim(-0.05, 1.05)
    ax.set_title("Economizer: outdoor air fraction vs outdoor temperature")
    fig.tight_layout()
    return fig
