from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# Paths
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

IDVG_DIR = ROOT / "data" / "idvg_fine"
FIG_DIR = ROOT / "figures"

RESULT_FILE = ROOT / "data" / "results_fine.csv"

MESH_FILE = (
    ROOT
    / "data"
    / "mesh_convergence"
    / "mesh_convergence_final.csv"
)

FIG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# Common plotting settings
# ============================================================

plt.rcParams.update(
    {
        "font.size": 12,
        "axes.labelsize": 13,
        "axes.titlesize": 15,
        "legend.fontsize": 11,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "figure.dpi": 120,
    }
)


# ============================================================
# Load baseline Lg = 0.5 um Id-Vg
# ============================================================

low_file = (
    IDVG_DIR
    / "idvg_Lg050_vd005.csv"
)

high_file = (
    IDVG_DIR
    / "idvg_Lg050_vd10.csv"
)

low = pd.read_csv(low_file)
high = pd.read_csv(high_file)

low = low.sort_values("Vg")
high = high.sort_values("Vg")

low["Id_abs"] = np.abs(low["Id"])
high["Id_abs"] = np.abs(high["Id"])


# ============================================================
# 1. Id-Vg linear
# ============================================================

plt.figure(
    figsize=(7.0, 5.2)
)

plt.plot(
    low["Vg"],
    low["Id_abs"],
    marker="o",
    markersize=4,
    label=r"$V_D=0.05$ V",
)

plt.plot(
    high["Vg"],
    high["Id_abs"],
    marker="s",
    markersize=4,
    label=r"$V_D=1.0$ V",
)

plt.xlabel(
    r"$V_G$ (V)"
)

plt.ylabel(
    r"$|I_D|$"
)

plt.title(
    r"$I_D-V_G$ Characteristics "
    r"($L_g=0.5\,\mu\mathrm{m}$)"
)

plt.grid(
    True,
    alpha=0.4,
)

plt.legend()

plt.tight_layout()

outfile = (
    FIG_DIR
    / "idvg_linear_fine.png"
)

plt.savefig(
    outfile,
    dpi=300,
    bbox_inches="tight",
)

plt.close()

print(
    f"Saved: {outfile}"
)


# ============================================================
# 2. Id-Vg semi-log
# ============================================================
plt.figure(
    figsize=(7.0, 5.2)
)

line_low, = plt.semilogy(
    low["Vg"],
    low["Id_abs"],
    marker="o",
    markersize=4,
    label=r"$V_D=0.05$ V",
)

line_high, = plt.semilogy(
    high["Vg"],
    high["Id_abs"],
    marker="s",
    markersize=4,
    label=r"$V_D=1.0$ V",
)


VTH_LOW = 0.186311
VTH_HIGH = 0.170735


plt.axvline(
    VTH_LOW,
    color=line_low.get_color(),
    linestyle="--",
    linewidth=1.8,
    alpha=0.8,
)

plt.axvline(
    VTH_HIGH,
    color=line_high.get_color(),
    linestyle="--",
    linewidth=1.8,
    alpha=0.8,
)


plt.text(
    VTH_LOW + 0.015,
    2e-3,
    rf"$V_{{th}}={VTH_LOW:.3f}$ V",
    rotation=90,
    color=line_low.get_color(),
    va="bottom",
)

plt.text(
    VTH_HIGH - 0.015,
    2e-4,
    rf"$V_{{th}}={VTH_HIGH:.3f}$ V",
    rotation=90,
    color=line_high.get_color(),
    va="bottom",
    ha="right",
)


plt.xlabel(
    r"$V_G$ (V)"
)

plt.ylabel(
    r"$|I_D|$"
)

plt.title(
    r"Subthreshold Characteristics "
    r"($L_g=0.5\,\mu\mathrm{m}$)"
)

plt.grid(
    True,
    which="both",
    alpha=0.35,
)

plt.legend()

plt.tight_layout()

outfile = (
    FIG_DIR
    / "idvg_semilog_fine.png"
)

plt.savefig(
    outfile,
    dpi=300,
    bbox_inches="tight",
)

plt.close()


# ============================================================
# 3. DIBL vs gate length
# ============================================================

results = pd.read_csv(
    RESULT_FILE
)

results = results.sort_values(
    "Lg_um"
)


plt.figure(
    figsize=(7.0, 5.2)
)

plt.plot(
    results["Lg_um"],
    results["DIBL_mV_V"],
    marker="o",
    markersize=7,
    linewidth=2,
)

plt.xlabel(
    r"$L_g$ ($\mu$m)"
)

plt.ylabel(
    "DIBL (mV/V)"
)

plt.title(
    "DIBL vs Gate Length"
)

plt.grid(
    True,
    alpha=0.4,
)

plt.tight_layout()

outfile = (
    FIG_DIR
    / "dibl_vs_lg_fine.png"
)

plt.savefig(
    outfile,
    dpi=300,
    bbox_inches="tight",
)

plt.close()

print(
    f"Saved: {outfile}"
)


# ============================================================
# 4. Mesh convergence
#
# Relative difference from ultrafine reference
# ============================================================

mesh = pd.read_csv(
    MESH_FILE
)

# Sort from coarse -> ultrafine
mesh = mesh.sort_values(
    "spacing_cm",
    ascending=False,
).reset_index(drop=True)


ultrafine = mesh[
    mesh["mesh"] == "ultrafine"
].iloc[0]


def relative_error(
    values,
    reference,
):

    return (
        np.abs(
            values - reference
        )
        /
        np.abs(reference)
        * 100.0
    )


mesh["Vth_error"] = (
    relative_error(
        mesh["Vth_V"],
        ultrafine["Vth_V"],
    )
)

mesh["Ion_error"] = (
    relative_error(
        mesh["Ion"],
        ultrafine["Ion"],
    )
)

mesh["SS_error"] = (
    relative_error(
        mesh["SS_mV_dec"],
        ultrafine["SS_mV_dec"],
    )
)


# Convert cm -> nm
mesh["spacing_nm"] = (
    mesh["spacing_cm"]
    * 1.0e7
)


plt.figure(
    figsize=(7.0, 5.2)
)

plt.plot(
    mesh["spacing_nm"],
    mesh["Vth_error"],
    marker="o",
    linewidth=2,
    label=r"$V_{\mathrm{th}}$",
)

plt.plot(
    mesh["spacing_nm"],
    mesh["Ion_error"],
    marker="s",
    linewidth=2,
    label=r"$I_{\mathrm{on}}$",
)

plt.plot(
    mesh["spacing_nm"],
    mesh["SS_error"],
    marker="^",
    linewidth=2,
    label="SS",
)


plt.xlabel(
    "Characteristic Mesh Spacing (nm)"
)

plt.ylabel(
    "Relative Difference from Ultrafine (%)"
)

plt.title(
    "Mesh Convergence"
)

plt.grid(
    True,
    alpha=0.4,
)

plt.legend()

# Coarse on left, fine on right
plt.gca().invert_xaxis()

plt.tight_layout()

outfile = (
    FIG_DIR
    / "mesh_convergence_fine.png"
)

plt.savefig(
    outfile,
    dpi=300,
    bbox_inches="tight",
)

plt.close()

print(
    f"Saved: {outfile}"
)


print()
print("=" * 60)
print("FINAL FIGURES GENERATED")
print("=" * 60)