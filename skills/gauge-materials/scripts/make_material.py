"""Create or rebuild a material from a preset and optionally assign it.

Usage (live):  run_blender_script path=skills/gauge-materials/scripts/make_material.py
               args={"name": "mat_steel", "preset": "brushed_metal", "color": "#b9bec6", "assign_to": "Housing",
                     "overrides": {"Roughness": 0.3}}
Args: name, preset (metal, brushed_metal, plastic, ceramic, rubber, glass, emissive, wood, concrete), color (sRGB hex),
      overrides (dict of Principled BSDF inputs by name), assign_to (object or collection name; replaces slot 0).
Rebuilding an existing material keeps every object that uses it. Prints one GAUGE_JSON line, gate "make-material".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge
import presets

P = gauge.params(globals(), name="mat", preset="plastic", color=None, overrides={}, assign_to=None)
mat = presets.make(P["name"], P["preset"], P["color"], **(P["overrides"] or {}))
assigned = []
if P["assign_to"]:
    for ob in gauge.pick(P["assign_to"]):
        if ob.data.materials:
            ob.data.materials[0] = mat
        else:
            ob.data.materials.append(mat)
        assigned.append(ob.name)
r = gauge.Report("make-material")
gauge.node_gate(r, mat.node_tree, mat.name)
r.info.update(material=mat.name, preset=P["preset"], assigned=assigned)
r.emit()
