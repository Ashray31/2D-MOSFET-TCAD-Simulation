# Copyright 2013 DEVSIM LLC
#
# SPDX-License-Identifier: Apache-2.0

import csv

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

from devsim import (
    element_from_edge_model,
    get_contact_current,
    get_contact_list,
    get_region_list,
    node_model,
    set_node_values,
    set_parameter,
    solve,
    write_devices,
)

from devsim.python_packages.model_create import CreateSolution


# ============================================================
# Create device / mesh
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
# 1. Electrostatic solution
# ============================================================

# Create electrostatic potential variable
for region in regions:
    CreateSolution(
        device,
        region,
        "Potential",
    )


# Silicon electrostatic models
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


# Oxide electrostatic model
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
# 2. Contacts
# ============================================================

contacts = get_contact_list(
    device=device
)

for contact in contacts:

    tmp = get_region_list(
        device=device,
        contact=contact,
    )

    region = tmp[0]

    print(
        f"Contact: {contact}, "
        f"Region: {region}"
    )

    CreateSiliconPotentialOnlyContact(
        device,
        region,
        contact,
    )

    # Initially all contacts are at 0 V
    set_parameter(
        device=device,
        name=GetContactBiasName(contact),
        value=0.0,
    )


# ============================================================
# 3. Silicon / oxide interfaces
# ============================================================

for interface in interfaces:

    CreateSiliconOxideInterface(
        device,
        interface,
    )


# ============================================================
# 4. Solve equilibrium electrostatics
# ============================================================

print("\n========================================")
print("Solving equilibrium electrostatics")
print("========================================")


solve(
    type="dc",
    absolute_error=1.0e-13,
    relative_error=1.0e-12,
    maximum_iterations=30,
)

solve(
    type="dc",
    absolute_error=1.0e-13,
    relative_error=1.0e-12,
    maximum_iterations=30,
)


write_devices(
    file="gmsh_mos2d_potentialonly",
    type="vtk",
)


# ============================================================
# 5. Add electrons / holes and drift-diffusion model
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


# Contact boundary conditions for drift-diffusion
for contact in contacts:

    tmp = get_region_list(
        device=device,
        contact=contact,
    )

    region = tmp[0]

    CreateSiliconDriftDiffusionAtContact(
        device,
        region,
        contact,
    )


# Initial drift-diffusion equilibrium
print("\n========================================")
print("Solving equilibrium drift-diffusion")
print("========================================")


solve(
    type="dc",
    absolute_error=1.0e30,
    relative_error=1.0e-5,
    maximum_iterations=100,
)


# ============================================================
# 6. Derived quantities
# ============================================================

for region in silicon_regions:

    node_model(
        device=device,
        region=region,
        name="logElectrons",
        equation="log(Electrons)/log(10)",
    )


for region in silicon_regions:

    element_from_edge_model(
        edge_model="ElectricField",
        device=device,
        region=region,
    )

    element_from_edge_model(
        edge_model="ElectronCurrent",
        device=device,
        region=region,
    )

    element_from_edge_model(
        edge_model="HoleCurrent",
        device=device,
        region=region,
    )


# ============================================================
# 7. Bias conditions
# ============================================================

# Source = 0 V
set_parameter(
    device=device,
    name=GetContactBiasName("source"),
    value=0.0,
)

# Body = 0 V
set_parameter(
    device=device,
    name=GetContactBiasName("body"),
    value=0.0,
)

# Gate starts from 0 V
set_parameter(
    device=device,
    name=GetContactBiasName("gate"),
    value=0.0,
)


# ============================================================
# Callback for rampbias
# ============================================================

def no_callback(device):
    """
    rampbias requires a callback after every successful
    intermediate bias step.

    We intentionally do nothing here because only the
    requested Id-Vg points are stored.
    """
    pass


# ============================================================
# 8. Ramp drain voltage from 0 V -> 1.0 V
# ============================================================

print("\n========================================")
print("Ramping drain voltage to 1.0 V")
print("========================================")


rampbias(
    device,
    "drain",
    1.0,       # final drain bias
    0.05,      # initial bias step
    1.0e-5,    # minimum allowed step
    100,       # maximum Newton iterations
    1.0e-5,    # relative error
    1.0e30,    # absolute error
    no_callback,
)


print("\nDrain successfully ramped to Vd = 1.0 V")


# ============================================================
# 9. Id-Vg sweep
# ============================================================

results = []


# Fine sweep for subthreshold region:
#
# 0.00, 0.02, ..., 0.40 V
vg_values = [
    0.02 * i
    for i in range(21)
]


# Moderately fine region:
#
# 0.45, 0.50, ..., 1.00 V
#
# This avoids jumping directly from 0.40 -> 0.50 V.
vg_values += [
    0.45 + 0.05 * i
    for i in range(12)
]


# Strong inversion:
#
# 1.10, 1.20, ..., 2.00 V
vg_values += [
    1.10 + 0.10 * i
    for i in range(10)
]


print("\n========================================")
print("Starting Id-Vg sweep at Vd = 1.0 V")
print("========================================")


for vg in vg_values:

    print(
        f"\n>>> Target Vg = {vg:.3f} V"
    )

    # --------------------------------------------------------
    # Adaptive gate-voltage continuation
    # --------------------------------------------------------
    #
    # Instead of:
    #
    #   set_parameter(...)
    #   solve(...)
    #
    # rampbias automatically reduces the voltage step if
    # Newton iteration fails.
    #
    rampbias(
        device,
        "gate",
        vg,         # target gate voltage
        0.02,       # initial step
        1.0e-5,     # minimum step
        100,        # maximum Newton iterations
        1.0e-5,     # required relative error
        1.0e30,     # absolute error
        no_callback,
    )


    # --------------------------------------------------------
    # Drain current
    # --------------------------------------------------------

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

    drain_current = (
        electron_current
        + hole_current
    )


    # Store only requested target voltage
    results.append(
        [
            vg,
            drain_current,
        ]
    )


    print(
        f">>> RESULT: "
        f"Vg = {vg:.3f} V, "
        f"Id = {drain_current:.6e}"
    )


# ============================================================
# 10. Save Id-Vg data
# ============================================================

output_csv = (
    "../data/idvg/"
    "idvg_Lg030_vd10.csv"
)


with open(
    output_csv,
    "w",
    newline="",
) as f:

    writer = csv.writer(f)

    writer.writerow(
        [
            "Vg",
            "Id",
        ]
    )

    writer.writerows(
        results
    )


print("\n========================================")
print("Id-Vg sweep completed")
print("========================================")

print(
    f"Saved CSV: {output_csv}"
)


# ============================================================
# 11. Save final device state
# ============================================================

write_devices(
    file="gmsh_mos2d_idvg_vd10.dat",
    type="tecplot",
)


write_devices(
    file="gmsh_mos2d_dd.dat",
    type="tecplot",
)


print(
    "Saved device state: "
    "gmsh_mos2d_idvg_vd10.dat"
)