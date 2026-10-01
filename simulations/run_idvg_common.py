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
# Settings
# ============================================================

VTH_CURRENT = 1.0e-4
SS_I_MIN = 1.0e-5

REL_ERROR = 1.0e-5
ABS_ERROR = 1.0e30
MAX_ITER = 100
MIN_STEP = 1.0e-6


# ============================================================
# Command line
# ============================================================

parser = argparse.ArgumentParser()

parser.add_argument(
    "--vd",
    type=float,
    required=True,
)

parser.add_argument(
    "--output",
    type=str,
    required=True,
)

args = parser.parse_args()

VD_TARGET = args.vd
OUTPUT_CSV = Path(args.output)


# ============================================================
# Create device from current mesh
# ============================================================

import gmsh_mos2d_create  # noqa: F401


device = "mos2d"

silicon_regions = ("gate", "bulk")
oxide_regions = ("oxide",)
regions = ("gate", "bulk", "oxide")

interfaces = (
    "bulk_oxide",
    "gate_oxide",
)


# ============================================================
# Electrostatic model
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
# Equilibrium electrostatics
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
# Drift-diffusion model
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


def ramp_gate(current_vg, target_vg):
    """
    Use the distance to the target as the initial continuation step.

    If Newton fails, rampbias automatically reduces the step.
    """

    delta = abs(target_vg - current_vg)

    if delta < 1.0e-12:
        return

    rampbias(
        device,
        "gate",
        target_vg,
        delta,
        MIN_STEP,
        MAX_ITER,
        REL_ERROR,
        ABS_ERROR,
        no_callback,
    )


# ============================================================
# Terminal biases
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
# Drain continuation
# ============================================================

print(
    f"\n=== Ramp drain to {VD_TARGET:.3f} V ==="
)


if VD_TARGET <= 0.1:
    vd_step = 0.01
else:
    vd_step = 0.05


rampbias(
    device,
    "drain",
    VD_TARGET,
    vd_step,
    MIN_STEP,
    MAX_ITER,
    REL_ERROR,
    ABS_ERROR,
    no_callback,
)


# ============================================================
# Measure Id at Vg = 0
# ============================================================

results = []

current_vg = 0.0

id_zero = measure_drain_current()

results.append(
    [0.0, id_zero]
)


print(
    f"Vg = 0.000 V, "
    f"Id = {id_zero:.8e}"
)


# ============================================================
# Optional negative-Vg extension
#
# Only required if Vth has already rolled below Vg = 0.
# ============================================================

need_negative = (
    abs(id_zero) > VTH_CURRENT
)


if need_negative:

    print(
        "\nNegative gate extension required "
        "because Id(Vg=0) > Vth criterion."
    )

    negative_limit = -0.50
    negative_step = -0.02

    vg = negative_step

    while vg >= negative_limit:

        print(
            f">>> Negative Vg = {vg:.3f} V"
        )

        ramp_gate(
            current_vg,
            vg,
        )

        current_vg = vg

        drain_current = (
            measure_drain_current()
        )

        results.append(
            [vg, drain_current]
        )

        print(
            f"Id = {drain_current:.8e}"
        )


        # Enough data for both Vth and SS extraction
        if abs(drain_current) <= SS_I_MIN:

            print(
                "Negative sweep reached "
                "the SS lower-current region."
            )

            break

        vg = round(
            vg + negative_step,
            10,
        )


    # Return to zero BEFORE positive sweep.
    #
    # This is much cheaper than:
    # 0 -> 2 -> 0 -> negative
    print("\nReturning gate to 0 V")

    ramp_gate(
        current_vg,
        0.0,
    )

    current_vg = 0.0


# ============================================================
# Positive Id-Vg sweep
# ============================================================

positive_vg = []


# Fine sampling:
# 0.02 -> 0.40 V
positive_vg += [
    round(0.02 * i, 10)
    for i in range(1, 21)
]


# Medium sampling:
# 0.45 -> 1.00 V
positive_vg += [
    round(0.45 + 0.05 * i, 10)
    for i in range(12)
]


# Strong inversion:
# 1.05 -> 2.00 V
#
# Use 0.05-V saved points.
# This is more robust than jumping by 0.1 V,
# but still far faster than forcing internal 0.02-V steps.
positive_vg += [
    round(1.05 + 0.05 * i, 10)
    for i in range(20)
]


print(
    f"\n=== Positive Id-Vg sweep, "
    f"Vd={VD_TARGET:.3f} V ==="
)


for vg in positive_vg:

    print(
        f">>> Vg = {vg:.3f} V"
    )

    ramp_gate(
        current_vg,
        vg,
    )

    current_vg = vg

    drain_current = (
        measure_drain_current()
    )

    results.append(
        [vg, drain_current]
    )

    print(
        f"Id = {drain_current:.8e}"
    )


# ============================================================
# Sort and save
# ============================================================

results.sort(
    key=lambda row: row[0]
)


OUTPUT_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


with open(
    OUTPUT_CSV,
    "w",
    newline="",
) as f:

    writer = csv.writer(f)

    writer.writerow(
        ["Vg", "Id"]
    )

    writer.writerows(
        results
    )


print("\n=== Sweep completed ===")

print(
    f"Saved: {OUTPUT_CSV}"
)