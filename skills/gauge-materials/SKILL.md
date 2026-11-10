---
name: gauge-materials
description: Build and check PBR materials in Blender as node graphs - presets for metal, brushed metal, plastic, ceramic, rubber, glass, emissive, wood, concrete, a spec-based node builder, and a gate for colour spaces, albedo range, metallic and roughness. Use for any shader or material work.
---

# Gauge materials

Materials are node graphs; Gauge writes them as **specs** (plain dicts), builds them with `gauge.node_build`, and reads any existing graph back with `gauge.node_dump` / `gauge.node_text`. A spec round-trips: build -> dump -> build gives the same graph.

## Make
```
run_blender_script path=skills/gauge-materials/scripts/make_material.py
  args={"name":"mat_steel","preset":"brushed_metal","color":"#b9bec6","assign_to":"Housing","overrides":{"Roughness":0.3}}
```
Presets (`scripts/presets.py`): `metal`, `brushed_metal` (anisotropic streaks, procedural), `plastic`, `ceramic`, `rubber`, `glass`, `emissive`, `wood`, `concrete`. Procedural ones use object coordinates, so they need no UVs. Re-running with the same name rebuilds in place and every user keeps it. `color` is an sRGB hex; `overrides` are Principled inputs by name.

Custom graph: write a spec `{"nodes": {key: {"type", "set", "in", "at"}}, "links": [["a.Out","b.In"]]}`; colours as `"#rrggbb"` are converted to linear for you; datablock sockets take names.

## Read before you edit
`gauge.node_text(material.node_tree)` (or the MCP `get_node_tree`) prints data-flow order with only the values that differ from a fresh node. `gauge.node_dump` gives the JSON spec.

## Gate
`scripts/material_gate.py` -> gate `material-health`.
- **Errors:** invalid links, output not connected, Image Texture without an image, data textures (roughness, metallic, normal, height) not in `Non-Color`.
- **Warnings:** unused nodes, muted nodes, albedo outside sRGB 30-240, metallic strictly between 0.05 and 0.95, roughness below 0.02, empty material slots.

## Judge the look
`scripts/swatch_sheet.py` renders one sphere per preset on a neutral studio and checks that no two look the same. Run it headless; a quick live check should use `percent` 40.

## Rules
- Metallic is a class: 0 or 1, blend with a mask. Dielectric albedo stays between sRGB 30 and 240.
- Roughness carries most of the realism: vary it with a noise or map range instead of a constant.
- Colour data (base colour, emission) is sRGB; everything else is Non-Color.
- Do not set `material.use_nodes` (deprecated in 5.x; node trees exist by default).
- Name by purpose: `mat_brushed_steel`, not `Material.003`.
