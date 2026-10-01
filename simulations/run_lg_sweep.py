import re
import sys
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# Paths
# ============================================================

SIM_DIR = Path(__file__).resolve().parent
ROOT = SIM_DIR.parent

DATA_DIR = ROOT / "data"
IDVG_DIR = DATA_DIR / "idvg"
LOG_DIR = DATA_DIR / "logs"
FIG_DIR = ROOT / "figures"

GEO_FILE = SIM_DIR / "gmsh_mos2d.geo"
CREATE_FILE = SIM_DIR / "gmsh_mos2d_create.py"
MESH_FILE = SIM_DIR / "gmsh_mos2d.msh"

RUNNER_FILE = (
    SIM_DIR / "run_idvg_common.py"
)


for directory in (
    DATA_DIR,
    IDVG_DIR,
    LOG_DIR,
    FIG_DIR,
):

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# Sweep settings
# ============================================================

LG_LIST_UM = [
    0.2,
    0.3,
    0.5,
    0.7,
    0.8,
]


VD_LOW = 0.05
VD_HIGH = 1.0


VTH_CURRENT = 1.0e-4

SS_I_MIN = 1.0e-5
SS_I_MAX = 1.0e-3

VG_OFF = 0.0
VG_ON = 2.0


# ============================================================
# External tools
# ============================================================

GMSH = shutil.which("gmsh")

if GMSH is None:
    raise RuntimeError(
        "gmsh command not found."
    )


if not RUNNER_FILE.exists():
    raise FileNotFoundError(
        RUNNER_FILE
    )


# ============================================================
# Utility
# ============================================================

def lg_tag(lg_um):

    return f"{int(round(lg_um * 100)):03d}"


# ============================================================
# Modify geometry
# ============================================================

def set_gate_width_geo(
    text,
    width_cm,
):

    pattern = (
        r"(?m)^"
        r"(\s*gate_width\s*=\s*)"
        r"[0-9.eE+\-]+"
        r"(\s*;.*)$"
    )

    new_text, count = re.subn(
        pattern,
        rf"\g<1>{width_cm:.8e}\g<2>",
        text,
        count=1,
    )

    if count != 1:

        raise RuntimeError(
            "Failed to modify "
            "gate_width in .geo"
        )

    return new_text



def set_gate_width_python(
    text,
    width_cm,
):

    pattern = (
        r"(?m)^"
        r"(\s*gate_width\s*=\s*)"
        r"[0-9.eE+\-]+"
        r"(\s*(?:#.*)?)$"
    )

    new_text, count = re.subn(
        pattern,
        rf"\g<1>{width_cm:.8e}\g<2>",
        text,
        count=1,
    )

    if count != 1:

        raise RuntimeError(
            "Failed to modify "
            "gate_width in Python file"
        )

    return new_text


# ============================================================
# Mesh
# ============================================================

def regenerate_mesh():

    command = [
        GMSH,
        str(GEO_FILE),
        "-2",
        "-format",
        "msh2",
        "-o",
        str(MESH_FILE),
    ]

    print(
        "\nGmsh:",
        " ".join(command),
    )

    subprocess.run(
        command,
        cwd=SIM_DIR,
        check=True,
    )


# ============================================================
# Load curve
# ============================================================

def load_curve(filename):

    df = pd.read_csv(
        filename
    )

    if not {
        "Vg",
        "Id",
    }.issubset(df.columns):

        raise ValueError(
            f"Invalid CSV columns: "
            f"{filename}"
        )


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
# Check whether an old curve can be reused
# ============================================================

def curve_usable(filename):

    if not filename.exists():
        return False


    try:

        vg, id_ = load_curve(
            filename
        )

    except Exception:
        return False


    if len(vg) < 10:
        return False


    # Must contain Vg=0 and Vg=2
    if not np.any(
        np.isclose(vg, 0.0)
    ):
        return False


    if not np.any(
        np.isclose(vg, 2.0)
    ):
        return False


    # Vth criterion must be bracketed
    if not (
        id_.min()
        <= VTH_CURRENT
        <= id_.max()
    ):
        return False


    # Need at least 3 points for SS fitting
    ss_mask = (
        (id_ >= SS_I_MIN)
        &
        (id_ <= SS_I_MAX)
    )

    if int(ss_mask.sum()) < 3:
        return False


    return True


# ============================================================
# Run one curve
# ============================================================

def run_curve(
    lg_um,
    vd,
    output_file,
):

    if curve_usable(
        output_file
    ):

        print(
            f"Reuse existing: "
            f"{output_file.name}"
        )

        return


    if output_file.exists():

        print(
            f"Existing curve is incomplete; "
            f"recalculating: "
            f"{output_file.name}"
        )

        output_file.unlink()


    tag = lg_tag(
        lg_um
    )


    vd_tag = (
        "vd005"
        if vd < 0.1
        else "vd10"
    )


    log_file = (
        LOG_DIR
        / f"Lg{tag}_{vd_tag}.log"
    )


    command = [
        sys.executable,
        str(RUNNER_FILE),
        "--vd",
        str(vd),
        "--output",
        str(output_file),
    ]


    print(
        f"Running "
        f"Lg={lg_um:.2f} um, "
        f"Vd={vd:.2f} V"
    )

    print(
        f"Log: {log_file}"
    )


    with open(
        log_file,
        "w",
    ) as log:

        try:

            subprocess.run(
                command,
                cwd=SIM_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )

        except subprocess.CalledProcessError:

            print(
                f"\nSimulation failed: "
                f"{log_file}"
            )


            lines = (
                log_file
                .read_text(
                    errors="ignore"
                )
                .splitlines()
            )


            print(
                "\n--- Last 60 lines ---"
            )

            for line in lines[-60:]:
                print(line)


            raise


    if not curve_usable(
        output_file
    ):

        raise RuntimeError(
            f"Simulation finished, "
            f"but curve is not sufficient "
            f"for extraction: "
            f"{output_file}"
        )


# ============================================================
# Vth extraction
# ============================================================

def extract_vth(
    vg,
    id_,
    target=VTH_CURRENT,
):

    log_target = np.log10(
        target
    )

    log_id = np.log10(
        id_
    )


    # Find adjacent Vg points which
    # bracket the target current.
    candidates = []


    for i in range(
        len(vg) - 1
    ):

        y1 = log_id[i]
        y2 = log_id[i + 1]


        # Prefer an increasing Id(Vg) crossing
        if (
            y1 <= log_target <= y2
            and
            y2 > y1
        ):

            candidates.append(i)


    if not candidates:

        raise ValueError(
            f"Could not bracket "
            f"Vth current {target:.3e}. "
            f"Id range="
            f"[{id_.min():.3e}, "
            f"{id_.max():.3e}]"
        )


    i = candidates[0]


    x1 = vg[i]
    x2 = vg[i + 1]

    y1 = log_id[i]
    y2 = log_id[i + 1]


    fraction = (
        (log_target - y1)
        /
        (y2 - y1)
    )


    return (
        x1
        + fraction
        * (x2 - x1)
    )


# ============================================================
# SS
# ============================================================

def extract_ss(
    vg,
    id_,
):

    mask = (
        (id_ >= SS_I_MIN)
        &
        (id_ <= SS_I_MAX)
    )


    npoints = int(
        mask.sum()
    )


    if npoints < 3:

        raise ValueError(
            "Not enough points "
            "for SS fitting."
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


    y_fit = (
        slope * x
        + intercept
    )


    ss_res = np.sum(
        (y - y_fit) ** 2
    )

    ss_tot = np.sum(
        (y - np.mean(y)) ** 2
    )


    if ss_tot > 0:

        r2 = (
            1
            - ss_res / ss_tot
        )

    else:

        r2 = np.nan


    return (
        slope * 1000.0,
        r2,
        npoints,
    )


# ============================================================
# Other parameters
# ============================================================

def current_at_vg(
    vg,
    id_,
    target,
):

    return np.interp(
        target,
        vg,
        id_,
    )



def extract_gm(
    vg,
    id_,
):

    gm = np.gradient(
        id_,
        vg,
    )

    index = int(
        np.argmax(gm)
    )

    return (
        gm[index],
        vg[index],
    )



def extract_metrics(
    vg,
    id_,
):

    vth = extract_vth(
        vg,
        id_,
    )


    ss, ss_r2, ss_points = (
        extract_ss(
            vg,
            id_,
        )
    )


    gm_max, vg_gm_max = (
        extract_gm(
            vg,
            id_,
        )
    )


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


    return {
        "Vth": vth,
        "SS_mV_dec": ss,
        "SS_R2": ss_r2,
        "SS_points": ss_points,
        "Ion": ion,
        "Ioff": ioff,
        "Ion_Ioff": ion / ioff,
        "gm_max": gm_max,
        "Vg_gm_max": vg_gm_max,
    }


# ============================================================
# Original geometry
# ============================================================

original_geo = (
    GEO_FILE.read_text()
)

original_create = (
    CREATE_FILE.read_text()
)


# ============================================================
# Sweep
# ============================================================

results = []


try:

    for lg_um in LG_LIST_UM:

        print()
        print("=" * 70)

        print(
            f"Lg = {lg_um:.2f} um"
        )

        print("=" * 70)


        tag = lg_tag(
            lg_um
        )


        low_file = (
            IDVG_DIR
            / f"idvg_Lg{tag}_vd005.csv"
        )


        high_file = (
            IDVG_DIR
            / f"idvg_Lg{tag}_vd10.csv"
        )


        low_ready = curve_usable(
            low_file
        )

        high_ready = curve_usable(
            high_file
        )


        # ----------------------------------------
        # Only regenerate geometry if at least
        # one simulation is actually required.
        # ----------------------------------------

        if not (
            low_ready
            and high_ready
        ):

            lg_cm = (
                lg_um * 1.0e-4
            )


            GEO_FILE.write_text(
                set_gate_width_geo(
                    original_geo,
                    lg_cm,
                )
            )


            CREATE_FILE.write_text(
                set_gate_width_python(
                    original_create,
                    lg_cm,
                )
            )


            print(
                f"gate_width = "
                f"{lg_cm:.8e} cm"
            )


            regenerate_mesh()


        # ----------------------------------------
        # Run only missing / unusable curves
        # ----------------------------------------

        run_curve(
            lg_um,
            VD_LOW,
            low_file,
        )


        run_curve(
            lg_um,
            VD_HIGH,
            high_file,
        )


        # ----------------------------------------
        # Extraction
        # ----------------------------------------

        vg_low, id_low = (
            load_curve(
                low_file
            )
        )


        vg_high, id_high = (
            load_curve(
                high_file
            )
        )


        low = extract_metrics(
            vg_low,
            id_low,
        )


        high = extract_metrics(
            vg_high,
            id_high,
        )


        dibl = (
            (
                low["Vth"]
                - high["Vth"]
            )
            /
            (
                VD_HIGH
                - VD_LOW
            )
            * 1000.0
        )


        row = {

            "Lg_um":
                lg_um,

            "Vth_Vd005":
                low["Vth"],

            "Vth_Vd10":
                high["Vth"],

            "DIBL_mV_V":
                dibl,

            "SS_Vd005_mV_dec":
                low["SS_mV_dec"],

            "SS_Vd10_mV_dec":
                high["SS_mV_dec"],

            "SS_R2_Vd005":
                low["SS_R2"],

            "SS_R2_Vd10":
                high["SS_R2"],

            "Ion_Vd005":
                low["Ion"],

            "Ioff_Vd005":
                low["Ioff"],

            "Ion_Ioff_Vd005":
                low["Ion_Ioff"],

            "gm_max_Vd005":
                low["gm_max"],

            "Ion_Vd10":
                high["Ion"],

            "Ioff_Vd10":
                high["Ioff"],

            "Ion_Ioff_Vd10":
                high["Ion_Ioff"],

            "gm_max_Vd10":
                high["gm_max"],
        }


        results.append(
            row
        )


        # Save after every Lg
        pd.DataFrame(
            results
        ).to_csv(
            DATA_DIR
            / "results.csv",
            index=False,
        )


        print(
            f"\nVth(low)  = "
            f"{low['Vth']:.6f} V"
        )

        print(
            f"Vth(high) = "
            f"{high['Vth']:.6f} V"
        )

        print(
            f"SS         = "
            f"{low['SS_mV_dec']:.3f} "
            f"mV/dec"
        )

        print(
            f"DIBL       = "
            f"{dibl:.3f} mV/V"
        )


finally:

    # Restore original project geometry
    GEO_FILE.write_text(
        original_geo
    )

    CREATE_FILE.write_text(
        original_create
    )


    try:

        regenerate_mesh()

    except Exception as exc:

        print(
            "Warning: source files were restored "
            "but mesh regeneration failed:"
        )

        print(exc)


# ============================================================
# Final results
# ============================================================

result_df = (
    pd.DataFrame(results)
    .sort_values("Lg_um")
)


result_file = (
    DATA_DIR / "results.csv"
)


result_df.to_csv(
    result_file,
    index=False,
)


print()
print("=" * 70)
print("ALL Lg SWEEPS COMPLETED")
print("=" * 70)

print(
    result_df.to_string(
        index=False
    )
)


# ============================================================
# Figures
# ============================================================

# DIBL
plt.figure(
    figsize=(6, 4.5)
)

plt.plot(
    result_df["Lg_um"],
    result_df["DIBL_mV_V"],
    marker="o",
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

plt.grid(True)

plt.tight_layout()

plt.savefig(
    FIG_DIR
    / "dibl_vs_lg.png",
    dpi=300,
)

plt.close()


# Vth
plt.figure(
    figsize=(6, 4.5)
)

plt.plot(
    result_df["Lg_um"],
    result_df["Vth_Vd005"],
    marker="o",
    label=r"$V_D=0.05$ V",
)

plt.plot(
    result_df["Lg_um"],
    result_df["Vth_Vd10"],
    marker="s",
    label=r"$V_D=1.0$ V",
)

plt.xlabel(
    r"$L_g$ ($\mu$m)"
)

plt.ylabel(
    r"$V_{\mathrm{th}}$ (V)"
)

plt.title(
    "Threshold Voltage vs Gate Length"
)

plt.legend()
plt.grid(True)
plt.tight_layout()

plt.savefig(
    FIG_DIR
    / "vth_vs_lg.png",
    dpi=300,
)

plt.close()


# Ioff
plt.figure(
    figsize=(6, 4.5)
)

plt.semilogy(
    result_df["Lg_um"],
    result_df["Ioff_Vd005"],
    marker="o",
)

plt.xlabel(
    r"$L_g$ ($\mu$m)"
)

plt.ylabel(
    r"$I_{\mathrm{off}}$"
)

plt.title(
    "Off-State Current vs Gate Length"
)

plt.grid(
    True,
    which="both",
)

plt.tight_layout()

plt.savefig(
    FIG_DIR
    / "ioff_vs_lg.png",
    dpi=300,
)

plt.close()


print(
    f"\nSaved results: "
    f"{result_file}"
)

print(
    f"Saved figures in: "
    f"{FIG_DIR}"
)