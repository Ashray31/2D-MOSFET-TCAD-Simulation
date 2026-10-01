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
from devsim.python_packages.ramp import rampbias, printAllCurrents
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


import gmsh_mos2d_create  # noqa

device = "mos2d"
silicon_regions = ("gate", "bulk")
oxide_regions = ("oxide",)
regions = ("gate", "bulk", "oxide")
interfaces = ("bulk_oxide", "gate_oxide")

for i in regions:
    CreateSolution(device, i, "Potential")

for i in silicon_regions:
    SetSiliconParameters(device, i, 300)
    CreateSiliconPotentialOnly(device, i)

for i in oxide_regions:
    SetOxideParameters(device, i, 300)
    CreateOxidePotentialOnly(device, i, "log_damp")

### Set up contacts
contacts = get_contact_list(device=device)
for i in contacts:
    tmp = get_region_list(device=device, contact=i)
    r = tmp[0]
    print("%s %s" % (r, i))
    CreateSiliconPotentialOnlyContact(device, r, i)
    set_parameter(device=device, name=GetContactBiasName(i), value=0.0)

for i in interfaces:
    CreateSiliconOxideInterface(device, i)

solve(type="dc", absolute_error=1.0e-13, relative_error=1e-12, maximum_iterations=30)
solve(type="dc", absolute_error=1.0e-13, relative_error=1e-12, maximum_iterations=30)

write_devices(file="gmsh_mos2d_potentialonly", type="vtk")

for i in silicon_regions:
    CreateSolution(device, i, "Electrons")
    CreateSolution(device, i, "Holes")
    set_node_values(
        device=device, region=i, name="Electrons", init_from="IntrinsicElectrons"
    )
    set_node_values(device=device, region=i, name="Holes", init_from="IntrinsicHoles")
    CreateSiliconDriftDiffusion(device, i, "mu_n", "mu_p")

for c in contacts:
    tmp = get_region_list(device=device, contact=c)
    r = tmp[0]
    CreateSiliconDriftDiffusionAtContact(device, r, c)

solve(type="dc", absolute_error=1.0e30, relative_error=1e-5, maximum_iterations=30)

for r in silicon_regions:
    node_model(
        device=device, region=r, name="logElectrons", equation="log(Electrons)/log(10)"
    )


for r in silicon_regions:
    element_from_edge_model(edge_model="ElectricField", device=device, region=r)
    element_from_edge_model(edge_model="ElectronCurrent", device=device, region=r)
    element_from_edge_model(edge_model="HoleCurrent", device=device, region=r)

# ==========================================
# Id-Vg sweep
# ==========================================

# Source, body remain at 0 V
set_parameter(
    device=device,
    name=GetContactBiasName("source"),
    value=0.0,
)

set_parameter(
    device=device,
    name=GetContactBiasName("body"),
    value=0.0,
)

# Fix drain voltage at 0.05 V
# Gradually ramp drain from 0 V to 0.05 V
for vd in [0.01, 0.02, 0.03, 0.04, 0.05]:

    set_parameter(
        device=device,
        name=GetContactBiasName("drain"),
        value=vd,
    )

    solve(
        type="dc",
        absolute_error=1e30,
        relative_error=1e-5,
        maximum_iterations=100,
    )

    print(f"Drain ramp: Vd = {vd:.2f} V")

results = []

vg_values = []

# Fine sweep: subthreshold region
vg_values += [0.02 * i for i in range(21)]   # 0.00 ~ 0.40 V

# Coarse sweep: strong inversion region
vg_values += [0.5 + 0.1 * i for i in range(16)]  # 0.50 ~ 2.00 V

for vg in vg_values:

    set_parameter(
        device=device,
        name=GetContactBiasName("gate"),
        value=vg,
    )

    solve(
        type="dc",
        absolute_error=1e30,
        relative_error=1e-5,
        maximum_iterations=30,
    )

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

    drain_current = electron_current + hole_current

    results.append([vg, drain_current])

    print(
        f"Vg = {vg:.2f} V, "
        f"Id = {drain_current:.6e}"
    )


# Save data
with open("../data/idvg/idvg_Lg030_vd005.csv", "w", newline="") as f:

    writer = csv.writer(f)

    writer.writerow(["Vg", "Id"])

    writer.writerows(results)


write_devices(
    file="gmsh_mos2d_idvg_vd005.dat",
    type="tecplot",
)
#
write_devices(file="gmsh_mos2d_dd.dat", type="tecplot")
