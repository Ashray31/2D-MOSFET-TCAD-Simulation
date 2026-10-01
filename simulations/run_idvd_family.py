import sys
import subprocess
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


SIM_DIR = Path(__file__).resolve().parent
ROOT = SIM_DIR.parent

RUNNER = (
    SIM_DIR / "run_idvd_common.py"
)

DATA_DIR = (
    ROOT / "data" / "idvd_fine"
)

FIG_DIR = (
    ROOT / "figures"
)


DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FIG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


VG_LIST = [
    0.5,
    1.0,
    1.5,
    2.0,
]


# ============================================================
# Run four curves
# ============================================================

for vg in VG_LIST:

    tag = int(
        round(vg * 10)
    )

    output_file = (
        DATA_DIR
        / f"idvd_vg{tag:02d}.csv"
    )


    if output_file.exists():

        print(
            f"Reuse existing: "
            f"{output_file.name}"
        )

        continue


    command = [
        sys.executable,
        str(RUNNER),
        "--vg",
        str(vg),
        "--output",
        str(output_file),
    ]


    print()
    print("=" * 60)

    print(
        f"Running Id-Vd at "
        f"Vg = {vg:.2f} V"
    )

    print("=" * 60)


    subprocess.run(
        command,
        cwd=SIM_DIR,
        check=True,
    )


# ============================================================
# Plot
# ============================================================

plt.figure(
    figsize=(6.5, 4.8)
)


for vg in VG_LIST:

    tag = int(
        round(vg * 10)
    )

    filename = (
        DATA_DIR
        / f"idvd_vg{tag:02d}.csv"
    )


    df = pd.read_csv(
        filename
    )


    plt.plot(
        df["Vd"],
        abs(df["Id"]),
        marker="o",
        label=rf"$V_G={vg:.1f}$ V",
    )


plt.xlabel(
    r"$V_D$ (V)"
)

plt.ylabel(
    r"$|I_D|$"
)

plt.title(
    r"$I_D-V_D$ Output Characteristics"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


figure_file = (
    FIG_DIR
    / "idvd_family_fine.png"
)


plt.savefig(
    figure_file,
    dpi=300,
)

plt.close()


print()
print(
    f"Saved figure: "
    f"{figure_file}"
)