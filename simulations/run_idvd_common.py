import argparse
import csv
from pathlib import Path

from devsim.python_packages.simple_physics import (
    GetContactBiasName,
    SetOxideParameters,
    SetSiliconParameters,
    CreateSiliconPotentialOnly,
    CreateSiliconPotentialOnlyContact,
    CreateSiliconDriftDiffusion,
    CreateSiliconDriftDiffusionAtContact,
    CreateOxidePotentialOnly,
    CreateSiliconOxideInterface,
)

from devsim.python_packages.ramp import rampbias
from devsim.python_packages.model_create import CreateSolution

from devsim import (
    get_contact_current,
    get_contact_list,
    get_region_list,
    set_node_values,
    set_parameter,
    solve,
)


# ============================================================
# Numerical settings
# ============================================================

REL_ERROR = 1.0e-5
ABS_ERROR = 1.0e30
MAX_ITER = 120
MIN_STEP = 1.0e-6


# ============================================================
# Command line
# ============================================================

parser = argparse.ArgumentParser()

parser.add_argument(
    "--vg",
    type=float,
    required=True,
)

parser.add_argument(
    "--output",
    type=str,
    required=True,
)

args = parser.parse_args()

VG_TARGET = args.vg
OUTPUT_FILE = Path(args.output)


# ============================================================
# Create device
# ============================================================

import gmsh_mos2d_create  # noqa: F401


device = "mos2d"

silicon_regions = (
    "gate",
    "bulk",
)

oxide_regions = (
    "oxide",
)

regions = (
    "gate",
    "bulk",
    "oxide",
)

interfaces = (
    "bulk_oxide",
    "gate_oxide",
)


# ============================================================
# Potential model
# ============================================================

for region in regions:

    CreateSolution(
        device,
        region,
        "Potential",
    )


for region in silicon_regions:

    SetSiliconParameters(
        device,
        region,
        300,
    )

    CreateSiliconPotentialOnly(
        device,
        region,
    )


for region in oxide_regions:

    SetOxideParameters(
        device,
        region,
        300,
    )

    CreateOxidePotentialOnly(
        device,
        region,
        "log_damp",
    )


# ============================================================
# Contacts
# ============================================================

contacts = get_contact_list(
    device=device
)

for contact in contacts:

    region = get_region_list(
        device=device,
        contact=contact,
    )[0]

    CreateSiliconPotentialOnlyContact(
        device,
        region,
        contact,
    )

    set_parameter(
        device=device,
        name=GetContactBiasName(contact),
        value=0.0,
    )


# ============================================================
# Interfaces
# ============================================================

for interface in interfaces:

    CreateSiliconOxideInterface(
        device,
        interface,
    )


# ============================================================
# Electrostatic equilibrium
# ============================================================

print("\n=== Electrostatic equilibrium ===")

solve(
    type="dc",
    absolute_error=1.0e-13,
    relative_error=1.0e-12,
    maximum_iterations=50,
)

solve(
    type="dc",
    absolute_error=1.0e-13,
    relative_error=1.0e-12,
    maximum_iterations=50,
)


# ============================================================
# Drift-diffusion
# ============================================================

for region in silicon_regions:

    CreateSolution(
        device,
        region,
        "Electrons",
    )

    CreateSolution(
        device,
        region,
        "Holes",
    )

    set_node_values(
        device=device,
        region=region,
        name="Electrons",
        init_from="IntrinsicElectrons",
    )

    set_node_values(
        device=device,
        region=region,
        name="Holes",
        init_from="IntrinsicHoles",
    )

    CreateSiliconDriftDiffusion(
        device,
        region,
        "mu_n",
        "mu_p",
    )


for contact in contacts:

    region = get_region_list(
        device=device,
        contact=contact,
    )[0]

    CreateSiliconDriftDiffusionAtContact(
        device,
        region,
        contact,
    )


print("\n=== Drift-diffusion equilibrium ===")

solve(
    type="dc",
    absolute_error=ABS_ERROR,
    relative_error=REL_ERROR,
    maximum_iterations=MAX_ITER,
)


# ============================================================
# Helpers
# ============================================================

def no_callback(device):
    pass


def measure_drain_current():

    electron_current = get_contact_current(
        device=device,
        contact="drain",
        equation="ElectronContinuityEquation",
    )

    hole_current = get_contact_current(
        device=device,
        contact="drain",
        equation="HoleContinuityEquation",
    )

    return electron_current + hole_current


# ============================================================
# Initial biases
# ============================================================

for contact in (
    "source",
    "body",
    "gate",
    "drain",
):

    set_parameter(
        device=device,
        name=GetContactBiasName(contact),
        value=0.0,
    )


# ============================================================
# Ramp gate first
#
# Bias path:
# (Vg,Vd) = (0,0) -> (VG_TARGET,0)
# ============================================================

print(
    f"\n=== Ramp gate to {VG_TARGET:.2f} V ==="
)

rampbias(
    device,
    "gate",
    VG_TARGET,
    0.05,
    MIN_STEP,
    MAX_ITER,
    REL_ERROR,
    ABS_ERROR,
    no_callback,
)


# ============================================================
# Id-Vd sweep
# ============================================================

vd_values = [
    round(0.1 * i, 10)
    for i in range(21)
]
# 0.0 -> 2.0 V


results = []

current_vd = 0.0


# Vd = 0 point
id_zero = measure_drain_current()

results.append(
    [0.0, id_zero]
)

print(
    f"Vd = 0.00 V, "
    f"Id = {id_zero:.8e}"
)


for vd in vd_values[1:]:

    print(
        f">>> Target Vd = {vd:.2f} V"
    )

    step = abs(
        vd - current_vd
    )

    rampbias(
        device,
        "drain",
        vd,
        step,
        MIN_STEP,
        MAX_ITER,
        REL_ERROR,
        ABS_ERROR,
        no_callback,
    )

    current_vd = vd

    drain_current = (
        measure_drain_current()
    )

    results.append(
        [vd, drain_current]
    )

    print(
        f"Vd = {vd:.2f} V, "
        f"Id = {drain_current:.8e}"
    )


# ============================================================
# Save
# ============================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True,
)


with open(
    OUTPUT_FILE,
    "w",
    newline="",
) as f:

    writer = csv.writer(f)

    writer.writerow(
        [
            "Vd",
            "Id",
        ]
    )

    writer.writerows(
        results
    )


print(
    f"\nSaved: {OUTPUT_FILE}"
)