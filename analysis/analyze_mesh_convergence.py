from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# Paths
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = (
    ROOT
    / "data"
    / "mesh_convergence"
)


# ============================================================
# Extraction settings
# ============================================================

VTH_CURRENT = 1.0e-4

SS_I_MIN = 1.0e-5
SS_I_MAX = 1.0e-3


FILES = {
    "coarse": DATA_DIR / "idvg_coarse_vd005.csv",
    "medium": DATA_DIR / "idvg_medium_vd005.csv",
    "fine": DATA_DIR / "idvg_fine_vd005.csv",
    "ultrafine": DATA_DIR / "idvg_ultrafine_vd005.csv",
}

SPACING = {
    "coarse": 1.0e-5,
    "medium": 5.0e-6,
    "fine": 2.5e-6,
    "ultrafine": 1.25e-6,
}


# ============================================================
# Load curve
# ============================================================

def load_curve(filename):

    df = pd.read_csv(filename)

    vg = df["Vg"].to_numpy(
        dtype=float
    )

    id_ = np.abs(
        df["Id"].to_numpy(
            dtype=float
        )
    )

    order = np.argsort(vg)

    return (
        vg[order],
        id_[order],
    )


# ============================================================
# Threshold voltage
# ============================================================

def extract_vth(vg, id_):

    log_id = np.log10(id_)

    target = np.log10(
        VTH_CURRENT
    )

    for i in range(
        len(vg) - 1
    ):

        if (
            log_id[i]
            <= target
            <= log_id[i + 1]
            and
            log_id[i + 1]
            > log_id[i]
        ):

            fraction = (
                target - log_id[i]
            ) / (
                log_id[i + 1]
                - log_id[i]
            )

            return (
                vg[i]
                + fraction
                * (
                    vg[i + 1]
                    - vg[i]
                )
            )

    raise RuntimeError(
        "Vth criterion not bracketed."
    )


# ============================================================
# Subthreshold swing
# ============================================================

def extract_ss(vg, id_):

    mask = (
        (id_ >= SS_I_MIN)
        &
        (id_ <= SS_I_MAX)
    )

    if mask.sum() < 3:

        raise RuntimeError(
            "Not enough points for SS."
        )

    x = np.log10(
        id_[mask]
    )

    y = vg[mask]

    slope, intercept = (
        np.polyfit(
            x,
            y,
            1,
        )
    )

    fit = (
        slope * x
        + intercept
    )

    ss_res = np.sum(
        (y - fit) ** 2
    )

    ss_tot = np.sum(
        (y - y.mean()) ** 2
    )

    r2 = (
        1
        - ss_res / ss_tot
    )

    return (
        slope * 1000,
        r2,
    )


# ============================================================
# Extract all three meshes
# ============================================================

results = []


for mesh, filename in FILES.items():

    if not filename.exists():

        raise FileNotFoundError(
            filename
        )

    vg, id_ = load_curve(
        filename
    )

    vth = extract_vth(
        vg,
        id_,
    )

    ss, r2 = extract_ss(
        vg,
        id_,
    )

    ion = np.interp(
        2.0,
        vg,
        id_,
    )

    ioff = np.interp(
        0.0,
        vg,
        id_,
    )

    results.append(
        {
            "mesh": mesh,
            "spacing_cm":
                SPACING[mesh],
            "Vth_V":
                vth,
            "SS_mV_dec":
                ss,
            "SS_R2":
                r2,
            "Ion":
                ion,
            "Ioff":
                ioff,
        }
    )


df = pd.DataFrame(
    results
)


# ============================================================
# Medium vs fine
# ============================================================

fine = df[
    df["mesh"] == "fine"
].iloc[0]

ultrafine = df[
    df["mesh"] == "ultrafine"
].iloc[0]


def relative_difference(
    medium_value,
    fine_value,
):

    return (
        abs(
            fine_value
            - medium_value
        )
        /
        abs(fine_value)
        * 100
    )


dvth = relative_difference(
    fine["Vth_V"],
    ultrafine["Vth_V"],
)

dion = relative_difference(
    fine["Ion"],
    ultrafine["Ion"],
)

dioff = relative_difference(
    fine["Ioff"],
    ultrafine["Ioff"],
)

dss = relative_difference(
    fine["SS_mV_dec"],
    ultrafine["SS_mV_dec"],
)


# ============================================================
# Output
# ============================================================

print()
print("=" * 70)
print("MESH RESULTS")
print("=" * 70)

print(
    df.to_string(
        index=False
    )
)


print()
print("=" * 70)
print("FINE VS ULTRAFINE")
print("=" * 70)

print(
    f"ΔVth  = {dvth:.3f}%"
)

print(
    f"ΔIon  = {dion:.3f}%"
)

print(
    f"ΔIoff = {dioff:.3f}%"
)

print(
    f"ΔSS   = {dss:.3f}%"
)


output_file = (
    DATA_DIR
    / "mesh_convergence_final.csv"
)

df.to_csv(
    output_file,
    index=False,
)

print()
print(
    f"Saved: {output_file}"
)