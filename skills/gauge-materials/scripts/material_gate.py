"""Gate materials: node-graph health plus PBR sanity of the Principled values.

Usage (live):  run_blender_script path=skills/gauge-materials/scripts/material_gate.py args={"collection": "Props"}
Usage (file):  python run_headless.py material_gate.py --blend asset.blend
Args: collection (object/collection whose materials to check; default every material in use).
Checks: valid links, connected output, image nodes with images, data textures in Non-Color (errors);
        unused nodes, albedo outside sRGB 30-240 for non-metals, metallic strictly between 0.05 and 0.95 without a
        texture, roughness below 0.02 on opaque surfaces, empty material slots (warnings).
Prints one GAUGE_JSON line, gate "material-health".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge

P = gauge.params(globals(), collection=None)
r = gauge.Report("material-health")
objs = gauge.pick(P["collection"], mesh_only=True)
mats = []
for o in objs:
    for s in o.material_slots:
        if s.material and s.material not in mats:
            mats.append(s.material)
empty = sorted({o.name for o in objs for s in o.material_slots if not s.material})
r.check("empty_material_slots", empty[:8], not empty, "none", "assign or remove the slot", severity="warn")
r.check("materials_found", len(mats), len(mats) > 0, "> 0", "no materials on the selected objects")
for m in mats:
    if m.node_tree is None:
        r.check(f"{m.name}: has_node_tree", False, False, True)
        continue
    gauge.node_gate(r, m.node_tree, m.name)
    for n in m.node_tree.nodes:
        if n.bl_idname != "ShaderNodeBsdfPrincipled":
            continue
        base, met, rough = n.inputs["Base Color"], n.inputs["Metallic"], n.inputs["Roughness"]
        trans = n.inputs["Transmission Weight"].default_value
        emit = n.inputs["Emission Strength"].default_value
        if not base.is_linked and not met.is_linked and met.default_value < 0.5 and emit < 0.01 and trans < 0.5:
            c = base.default_value
            lum_srgb = gauge.to_srgb(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])
            r.check(f"{m.name}: albedo_range", round(lum_srgb, 3), 0.117 <= lum_srgb <= 0.94, "0.12 .. 0.94 (sRGB luma, = 30..240)",
                    "pure black/white albedo is not physical: keep sRGB albedo between 30 and 240",
                    severity="warn")
        if not met.is_linked:
            mv = met.default_value
            r.check(f"{m.name}: metallic_binary", round(mv, 3), mv <= 0.05 or mv >= 0.95, "0/1",
                    "metallic is a material class, not a slider: use 0 or 1 and blend with a mask", severity="warn")
        if not rough.is_linked and trans < 0.5 and emit < 0.01:
            r.check(f"{m.name}: roughness_floor", round(rough.default_value, 3), rough.default_value >= 0.02, ">= 0.02",
                    "perfect mirrors read as CG and alias; keep a little roughness", severity="warn")
r.info["materials"] = [m.name for m in mats]
r.emit()
