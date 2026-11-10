---
name: gauge-geonodes
description: Build Geometry Nodes setups in Blender from JSON specs and verify them by counting instances, measuring size and neighbour steps. Includes recipes for noise-lifted instanced grids, radial arrays and surface scatter, plus a modifier-input helper that works on Blender 5.x. Use for procedural geometry, instancing and landscapes.
---

# Gauge Geometry Nodes

Write the node graph as data, build it, set inputs by name, then **measure what it produced**.

## Recipes
`recipes/*.json` hold the whole group: interface (inputs with defaults and limits), nodes, links.

| Recipe | Makes | Inputs |
|---|---|---|
| `height_grid` | grid of points lifted by 4D noise, a cube instanced on each; noise stored as point attribute `height` (0..1) | Source, Width, Depth, Res X, Res Y, Amplitude, Noise Scale, Detail, Roughness, Seed, Cube Scale |
| `radial_array` | N copies around a circle, facing outward | Instance, Count, Radius, Scale |
| `scatter_surface` | copies over another object's surface, random size and spin | Target, Instance, Density, Seed, Min Scale, Max Scale |

```
run_blender_script path=skills/gauge-geonodes/scripts/gn_make.py
  args={"recipe":"height_grid","host":"Terrain","inputs":{"Res X":80,"Res Y":64,"Amplitude":0.4}}
```
Empty object inputs get a small generated mesh (the instance source is hidden but still instanced). Re-running rebuilds the group on the same host. Change values later with `gauge.gn_set(mod, Amplitude=0.6)`.

## Own graphs
Copy a recipe and edit it. Format (shared with materials):
```json
{"interface": {"inputs": [{"name": "Size", "type": "Float", "default": 1, "min": 0}], "outputs": [{"name": "Geometry", "type": "Geometry"}]},
 "nodes": {"gin": {"type": "NodeGroupInput"}, "grid": {"type": "GeometryNodeMeshGrid", "in": {"Vertices X": 20}}},
 "links": [["gin.Size", "grid.Size X"], ["grid.Mesh", "out.Geometry"]]}
```
`"set"` holds node properties (`{"noise_dimensions": "4D"}`), `"in"` holds unlinked input values. Use input *names* ("From Min"); duplicated names need the identifier (`Value_001`). Read any existing group with `scripts/gn_dump.py` (text, or a spec you can rebuild).

## Gate
`scripts/gn_gate.py` -> gate `geonodes-health`: tree valid and output connected, result not empty, `min_instances` / `max_instances`, `max_size`, `max_faces`, and `max_neighbour_step` (largest height jump between neighbouring cells of an instanced grid; the number that tells a landscape from static).

## Facts that bite
- Modifier inputs: `mod["Socket_1"] = v` fails on 5.x. Use `gauge.gn_set` / `gn_get`.
- Instances are not objects; count with `gauge.instance_count`. Hiding the source (viewport or render) does not change the count.
- An instance-only object has an empty bounding box: `gauge.size_of` measures through the instances.
- Attributes stored before **Instance on Points** reach the instances: read them in a shader with an Attribute node of type *Instancer*. `Object Info > Random` is independent per instance and looks like salt and pepper; a stored attribute follows the noise.
- Use a Map Range after noise to set amplitude and contrast: heights stay linear in it, so every neighbour step scales with the amplitude.
- Heavy results (tens of thousands of instances) belong in headless renders, not a live session.
