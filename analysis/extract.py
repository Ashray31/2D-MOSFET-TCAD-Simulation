import numpy as np
import pandas as pd
from pathlib import Path


# =========================================
# Paths
# =========================================
ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data" / "idvg"

LOW_FILE = DATA_DIR / "idvg_Lg030_vd005.csv"
HIGH_FILE = DATA_DIR / "idvg_Lg030_vd10.csv"


# =========================================
# Settings
# =========================================

# Constant-current threshold criterion
VTH_CURRENT = 1e-4

# Current window for SS fitting
SS_I_MIN = 1e-5
SS_I_MAX = 1e-3

VG_OFF = 0.0
VG_ON = 2.0


# =========================================
# Data loading
# =========================================
def load_curve(filename):
    df = pd.read_csv(filename)

    vg = df["Vg"].to_numpy(dtype=float)
    id_ = np.abs(df["Id"].to_numpy(dtype=float))

    return vg, id_


# =========================================
# Interpolation
# =========================================
def current_at_vg(vg, id_, vg_target):
    """
    Interpolate Id at a specified gate voltage.
    """
    return np.interp(vg_target, vg, id_)


# =========================================
# Threshold voltage
# =========================================
def extract_vth(vg, id_, current_target=VTH_CURRENT):
    """
    Constant-current Vth extraction.

    Interpolation is performed in log(Id), because
    the threshold region spans several decades.
    """

    if current_target < id_.min() or current_target > id_.max():
        raise ValueError(
            f"Target current {current_target:.3e} "
            "is outside the simulated current range."
        )

    log_id = np.log10(id_)

    # Sort by current to make interpolation robust
    order = np.argsort(log_id)

    vth = np.interp(
        np.log10(current_target),
        log_id[order],
        vg[order],
    )

    return vth


# =========================================
# Subthreshold swing
# =========================================
def extract_ss(
    vg,
    id_,
    current_min=SS_I_MIN,
    current_max=SS_I_MAX,
):
    """
    Fit:
        Vg = a * log10(Id) + b

    SS = a * 1000 [mV/dec]
    """

    mask = (
        (id_ >= current_min)
        & (id_ <= current_max)
    )

    if mask.sum() < 3:
        raise ValueError(
            "Not enough points in SS fitting region."
        )

    x = np.log10(id_[mask])
    y = vg[mask]

    slope, intercept = np.polyfit(x, y, 1)

    y_fit = slope * x + intercept

    ss_res = np.sum((y - y_fit) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)

    r2 = 1.0 - ss_res / ss_tot

    ss = slope * 1000.0

    return ss, r2, mask.sum()


# =========================================
# Transconductance
# =========================================
def extract_gm(vg, id_):
    """
    Numerical derivative:
        gm = dId / dVg
    """

    gm = np.gradient(id_, vg)

    index = np.argmax(gm)

    return {
        "gm_max": gm[index],
        "vg_at_gm_max": vg[index],
        "gm_curve": gm,
    }


# =========================================
# Extract all metrics from one Id-Vg curve
# =========================================
def extract_metrics(vg, id_):

    vth = extract_vth(vg, id_)

    ss, ss_r2, ss_points = extract_ss(vg, id_)

    gm_result = extract_gm(vg, id_)

    ioff = current_at_vg(
        vg,
        id_,
        VG_OFF,
    )

    ion = current_at_vg(
        vg,
        id_,
        VG_ON,
    )

    ion_ioff = ion / ioff

    return {
        "Vth": vth,
        "SS_mV_dec": ss,
        "SS_R2": ss_r2,
        "SS_points": ss_points,
        "Ion": ion,
        "Ioff": ioff,
        "Ion_Ioff": ion_ioff,
        "gm_max": gm_result["gm_max"],
        "Vg_gm_max": gm_result["vg_at_gm_max"],
    }


# =========================================
# Main
# =========================================
vg_low, id_low = load_curve(LOW_FILE)
vg_high, id_high = load_curve(HIGH_FILE)

low = extract_metrics(vg_low, id_low)
high = extract_metrics(vg_high, id_high)


# DIBL
vd_low = 0.05
vd_high = 1.0

dibl_v_per_v = (
    low["Vth"] - high["Vth"]
) / (vd_high - vd_low)

dibl_mv_per_v = dibl_v_per_v * 1000.0


# =========================================
# Print
# =========================================
print()
print("=" * 55)
print("Si nMOSFET Parameter Extraction")
print("=" * 55)

print()
print("Vd = 0.05 V")
print("-" * 30)

for key, value in low.items():
    print(f"{key:15s}: {value:.6g}")


print()
print("Vd = 1.00 V")
print("-" * 30)

for key, value in high.items():
    print(f"{key:15s}: {value:.6g}")


print()
print("DIBL")
print("-" * 30)

print(
    f"DIBL = {dibl_mv_per_v:.3f} mV/V"
)


# =========================================
# Save summary
# =========================================
summary = pd.DataFrame(
    [
        {
            "Vd": 0.05,
            **low,
        },
        {
            "Vd": 1.0,
            **high,
        },
    ]
)

summary["DIBL_mV_V"] = np.nan
summary.loc[0, "DIBL_mV_V"] = dibl_mv_per_v


output_file = DATA_DIR / "parameter_summary.csv"

summary.to_csv(
    output_file,
    index=False,
)

print()
print("Saved:")
print(output_file)