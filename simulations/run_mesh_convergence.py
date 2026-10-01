import re
import sys
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# Paths
# ============================================================

SIM_DIR = Path(__file__).resolve().parent
ROOT = SIM_DIR.parent

DATA_DIR = ROOT / "data" / "mesh_convergence"
DATA_DIR.mkdir(parents=True, exist_ok=True)

GEO_FILE = SIM_DIR / "gmsh_mos2d.geo"
CREATE_FILE = SIM_DIR / "gmsh_mos2d_create.py"
MESH_FILE = SIM_DIR / "gmsh_mos2d.msh"

RUNNER = SIM_DIR / "run_idvg_common.py"


# ============================================================
# Device parameters
# ============================================================

LG_CM = 5.0e-5        # 0.5 um

VD = 0.05

VTH_CURRENT = 1.0e-4

SS_I_MIN = 1.0e-5
SS_I_MAX = 1.0e-3


# ============================================================
# Mesh cases
# ============================================================

MESH_CASES = {
    "coarse": 1.0e-5,
    "medium": 5.0e-6,
    "fine": 2.5e-6,
    "ultrafine": 1.25e-6,
}


# ============================================================
# Text replacement utilities
# ============================================================

def replace_geo_parameter(text, name, value):

    pattern = (
        rf"(?m)^"
        rf"(\s*{re.escape(name)}\s*=\s*)"
        rf"[0-9.eE+\-]+"
        rf"(\s*;.*)$"
    )

    new_text, count = re.subn(
        pattern,
        rf"\g<1>{value:.8e}\g<2>",
        text,
        count=1,
    )

    if count != 1:
        raise RuntimeError(
            f"Could not replace {name} in gmsh_mos2d.geo"
        )

    return new_text


def replace_python_parameter(text, name, value):

    pattern = (
        rf"(?m)^"
        rf"(\s*{re.escape(name)}\s*=\s*)"
        rf"[0-9.eE+\-]+"
        rf"(\s*(?:#.*)?)$"
    )

    new_text, count = re.subn(
        pattern,
        rf"\g<1>{value:.8e}\g<2>",
        text,
        count=1,
    )

    if count != 1:
        raise RuntimeError(
            f"Could not replace {name} "
            f"in gmsh_mos2d_create.py"
        )

    return new_text


# ============================================================
# Mesh statistics
# ============================================================

def read_msh2_counts(filename):

    lines = filename.read_text().splitlines()

    node_count = None
    element_count = None

    for i, line in enumerate(lines):

        if line.strip() == "$Nodes":
            node_count = int(lines[i + 1])

        if line.strip() == "$Elements":
            element_count = int(lines[i + 1])

    return node_count, element_count


# ============================================================
# Curve loading
# ============================================================

def load_curve(filename):

    df = pd.read_csv(filename)

    vg = df["Vg"].to_numpy(dtype=float)
    id_ = np.abs(
        df["Id"].to_numpy(dtype=float)
    )

    order = np.argsort(vg)

    return vg[order], id_[order]


# ============================================================
# Vth extraction
# ============================================================

def extract_vth(vg, id_):

    target_log = np.log10(VTH_CURRENT)

    log_id = np.log10(id_)

    for i in range(len(vg) - 1):

        y1 = log_id[i]
        y2 = log_id[i + 1]

        if (
            y1 <= target_log <= y2
            and y2 > y1
        ):

            fraction = (
                (target_log - y1)
                /
                (y2 - y1)
            )

            return (
                vg[i]
                + fraction
                * (vg[i + 1] - vg[i])
            )

    raise RuntimeError(
        "Could not extract Vth."
    )


# ============================================================
# SS extraction
# ============================================================

def extract_ss(vg, id_):

    mask = (
        (id_ >= SS_I_MIN)
        &
        (id_ <= SS_I_MAX)
    )

    if mask.sum() < 3:
        raise RuntimeError(
            "Not enough data for SS fitting."
        )

    x = np.log10(id_[mask])
    y = vg[mask]

    slope, intercept = np.polyfit(
        x,
        y,
        1,
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

    r2 = (
        1.0 - ss_res / ss_tot
    )

    return slope * 1000.0, r2


# ============================================================
# Current at gate voltage
# ============================================================

def current_at_vg(vg, id_, target):

    return np.interp(
        target,
        vg,
        id_,
    )


# ============================================================
# Save originals
# ============================================================

original_geo = GEO_FILE.read_text()
original_create = CREATE_FILE.read_text()


results = []


# ============================================================
# Main
# ============================================================

try:

    for case, spacing in MESH_CASES.items():

        print()
        print("=" * 65)
        print(f"MESH CASE: {case}")
        print("=" * 65)

        print(
            f"x_diffusion_spacing = "
            f"{spacing:.3e} cm"
        )

        # ----------------------------------------------------
        # Enforce baseline geometry
        # ----------------------------------------------------

        geo_text = original_geo

        geo_text = replace_geo_parameter(
            geo_text,
            "gate_width",
            LG_CM,
        )

        geo_text = replace_geo_parameter(
            geo_text,
            "x_diffusion_spacing",
            spacing,
        )

        GEO_FILE.write_text(
            geo_text
        )


        create_text = (
            replace_python_parameter(
                original_create,
                "gate_width",
                LG_CM,
            )
        )

        CREATE_FILE.write_text(
            create_text
        )


        # ----------------------------------------------------
        # Generate mesh
        # ----------------------------------------------------

        command = [
            "gmsh",
            str(GEO_FILE),
            "-2",
            "-format",
            "msh2",
            "-o",
            str(MESH_FILE),
        ]

        print("\nGenerating mesh...")

        subprocess.run(
            command,
            cwd=SIM_DIR,
            check=True,
        )


        node_count, element_count = (
            read_msh2_counts(
                MESH_FILE
            )
        )

        print(
            f"Nodes    = {node_count}"
        )

        print(
            f"Elements = {element_count}"
        )


        # ----------------------------------------------------
        # Run Id-Vg
        # ----------------------------------------------------

        output_file = (
            DATA_DIR
            / f"idvg_{case}_vd005.csv"
        )

        if output_file.exists():

            print(
            f"Reuse existing mesh result: "
            f"{output_file.name}"
            )

        else:

            print("\nRunning Id-Vg...")

            subprocess.run(
            [
            sys.executable,
            str(RUNNER),
            "--vd",
            str(VD),
            "--output",
            str(output_file),
            ],
            cwd=SIM_DIR,
            check=True,
                )


        # ----------------------------------------------------
        # Extract parameters
        # ----------------------------------------------------

        vg, id_ = load_curve(
            output_file
        )


        vth = extract_vth(
            vg,
            id_,
        )


        ss, ss_r2 = extract_ss(
            vg,
            id_,
        )


        ion = current_at_vg(
            vg,
            id_,
            2.0,
        )


        ioff = current_at_vg(
            vg,
            id_,
            0.0,
        )


        results.append(
            {
                "mesh": case,
                "x_spacing_cm": spacing,
                "nodes": node_count,
                "elements": element_count,
                "Vth_V": vth,
                "SS_mV_dec": ss,
                "SS_R2": ss_r2,
                "Ion": ion,
                "Ioff": ioff,
            }
        )


        print()
        print(
            f"Vth = {vth:.8f} V"
        )

        print(
            f"SS   = {ss:.4f} mV/dec"
        )

        print(
            f"Ion  = {ion:.8e}"
        )


finally:

    # ========================================================
    # Restore project
    # ========================================================

    print(
        "\nRestoring original geometry..."
    )

    GEO_FILE.write_text(
        original_geo
    )

    CREATE_FILE.write_text(
        original_create
    )


    subprocess.run(
        [
            "gmsh",
            str(GEO_FILE),
            "-2",
            "-format",
            "msh2",
            "-o",
            str(MESH_FILE),
        ],
        cwd=SIM_DIR,
        check=True,
    )


# ============================================================
# Results
# ============================================================

df = pd.DataFrame(results)

if len(df) != len(MESH_CASES):
    raise RuntimeError(
        f"Expected {len(MESH_CASES)} mesh cases, "
        f"but only {len(df)} were completed."
    )


# ============================================================
# Save raw convergence results
# ============================================================

output_summary = (
    DATA_DIR
    / "mesh_convergence.csv"
)

df.to_csv(
    output_summary,
    index=False,
)


print()
print("=" * 65)
print("ALL MESH RESULTS")
print("=" * 65)

print(
    df.to_string(
        index=False
    )
)


# ============================================================
# Select medium / fine
# ============================================================

medium_rows = df[
    df["mesh"] == "medium"
]

fine_rows = df[
    df["mesh"] == "fine"
]


if len(medium_rows) != 1:
    raise RuntimeError(
        "Medium mesh result is missing or duplicated."
    )

if len(fine_rows) != 1:
    raise RuntimeError(
        "Fine mesh result is missing or duplicated."
    )


medium = medium_rows.iloc[0]
fine = fine_rows.iloc[0]


# ============================================================
# Relative differences: medium vs fine
# ============================================================

dvth = (
    abs(
        fine["Vth_V"]
        - medium["Vth_V"]
    )
    /
    abs(fine["Vth_V"])
    * 100.0
)


dion = (
    abs(
        fine["Ion"]
        - medium["Ion"]
    )
    /
    abs(fine["Ion"])
    * 100.0
)


dss = (
    abs(
        fine["SS_mV_dec"]
        - medium["SS_mV_dec"]
    )
    /
    abs(fine["SS_mV_dec"])
    * 100.0
)


dioff = (
    abs(
        fine["Ioff"]
        - medium["Ioff"]
    )
    /
    abs(fine["Ioff"])
    * 100.0
)


# ============================================================
# Add convergence summary
# ============================================================

summary_df = pd.DataFrame(
    [
        {
            "comparison": "medium_vs_fine",
            "delta_Vth_percent": dvth,
            "delta_Ion_percent": dion,
            "delta_Ioff_percent": dioff,
            "delta_SS_percent": dss,
        }
    ]
)


summary_file = (
    DATA_DIR
    / "mesh_convergence_summary.csv"
)

summary_df.to_csv(
    summary_file,
    index=False,
)


# ============================================================
# Print summary
# ============================================================

print()
print("=" * 65)
print("MESH CONVERGENCE: MEDIUM VS FINE")
print("=" * 65)

print(
    f"Medium nodes : "
    f"{int(medium['nodes'])}"
)

print(
    f"Fine nodes   : "
    f"{int(fine['nodes'])}"
)

print()

print(
    f"Vth medium = "
    f"{medium['Vth_V']:.8f} V"
)

print(
    f"Vth fine   = "
    f"{fine['Vth_V']:.8f} V"
)

print(
    f"ΔVth       = "
    f"{dvth:.3f}%"
)

print()

print(
    f"Ion medium = "
    f"{medium['Ion']:.8e}"
)

print(
    f"Ion fine   = "
    f"{fine['Ion']:.8e}"
)

print(
    f"ΔIon       = "
    f"{dion:.3f}%"
)

print()

print(
    f"Ioff medium = "
    f"{medium['Ioff']:.8e}"
)

print(
    f"Ioff fine   = "
    f"{fine['Ioff']:.8e}"
)

print(
    f"ΔIoff       = "
    f"{dioff:.3f}%"
)

print()

print(
    f"SS medium = "
    f"{medium['SS_mV_dec']:.4f} mV/dec"
)

print(
    f"SS fine   = "
    f"{fine['SS_mV_dec']:.4f} mV/dec"
)

print(
    f"ΔSS       = "
    f"{dss:.3f}%"
)


print()
print(
    f"Saved mesh data: "
    f"{output_summary}"
)

print(
    f"Saved convergence summary: "
    f"{summary_file}"
)