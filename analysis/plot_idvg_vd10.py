import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


data_dir = Path("../data/idvg")
fig_dir = Path("../figures")
fig_dir.mkdir(exist_ok=True)


# ==============================
# Read data
# ==============================
df_low = pd.read_csv(data_dir / "idvg_vd005.csv")
df_high = pd.read_csv(data_dir / "idvg_vd10.csv")

vg_low = df_low["Vg"].to_numpy()
id_low = np.abs(df_low["Id"].to_numpy())

vg_high = df_high["Vg"].to_numpy()
id_high = np.abs(df_high["Id"].to_numpy())


# ==============================
# 1. Vd = 0.05 V linear
# ==============================
plt.figure(figsize=(6, 4.5))

plt.plot(vg_low, id_low, marker="o")

plt.xlabel(r"$V_G$ (V)")
plt.ylabel(r"$I_D$")
plt.title(r"$I_D-V_G$ at $V_D=0.05$ V")

plt.grid(True)
plt.tight_layout()

plt.savefig(
    fig_dir / "idvg_vd005_linear.png",
    dpi=300
)

plt.close()


# ==============================
# 2. Vd = 0.05 V log
# ==============================
plt.figure(figsize=(6, 4.5))

plt.semilogy(vg_low, id_low, marker="o")

plt.xlabel(r"$V_G$ (V)")
plt.ylabel(r"$|I_D|$")
plt.title(r"$I_D-V_G$ at $V_D=0.05$ V")

plt.grid(True, which="both")
plt.tight_layout()

plt.savefig(
    fig_dir / "idvg_vd005_log.png",
    dpi=300
)

plt.close()


# ==============================
# 3. Vd = 1.0 V linear
# ==============================
plt.figure(figsize=(6, 4.5))

plt.plot(vg_high, id_high, marker="o")

plt.xlabel(r"$V_G$ (V)")
plt.ylabel(r"$I_D$")
plt.title(r"$I_D-V_G$ at $V_D=1.0$ V")

plt.grid(True)
plt.tight_layout()

plt.savefig(
    fig_dir / "idvg_vd10_linear.png",
    dpi=300
)

plt.close()


# ==============================
# 4. Vd = 1.0 V log
# ==============================
plt.figure(figsize=(6, 4.5))

plt.semilogy(vg_high, id_high, marker="o")

plt.xlabel(r"$V_G$ (V)")
plt.ylabel(r"$|I_D|$")
plt.title(r"$I_D-V_G$ at $V_D=1.0$ V")

plt.grid(True, which="both")
plt.tight_layout()

plt.savefig(
    fig_dir / "idvg_vd10_log.png",
    dpi=300
)

plt.close()


# ==============================
# 5. Compare low/high Vd
# ==============================
plt.figure(figsize=(6, 4.5))

plt.semilogy(
    vg_low,
    id_low,
    marker="o",
    label=r"$V_D=0.05$ V"
)

plt.semilogy(
    vg_high,
    id_high,
    marker="s",
    label=r"$V_D=1.0$ V"
)

plt.xlabel(r"$V_G$ (V)")
plt.ylabel(r"$|I_D|$")
plt.title(r"$I_D-V_G$ comparison")

plt.legend()
plt.grid(True, which="both")
plt.tight_layout()

plt.savefig(
    fig_dir / "idvg_dibl_comparison.png",
    dpi=300
)

plt.close()


print("Figures saved in:", fig_dir)