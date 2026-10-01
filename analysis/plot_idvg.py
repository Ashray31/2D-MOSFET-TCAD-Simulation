import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


data_file = Path("../data/idvg/idvg_vd005.csv")
fig_dir = Path("../figures")

fig_dir.mkdir(exist_ok=True)

df = pd.read_csv(data_file)

vg = df["Vg"].to_numpy()
id_ = np.abs(df["Id"].to_numpy())


# ==============================
# Linear Id-Vg
# ==============================
plt.figure(figsize=(6, 4.5))

plt.plot(vg, id_, marker="o")

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
# Semi-log Id-Vg
# ==============================
plt.figure(figsize=(6, 4.5))

plt.semilogy(vg, id_, marker="o")

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


print("Saved:")
print(fig_dir / "idvg_vd005_linear.png")
print(fig_dir / "idvg_vd005_log.png")