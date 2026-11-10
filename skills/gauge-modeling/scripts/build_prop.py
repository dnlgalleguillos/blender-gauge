"""Build a hard-surface prop from a parts list and gate it. Idempotent: rebuilding replaces the collection.

Usage (live):  run_blender_script path=skills/gauge-modeling/scripts/build_prop.py args={"name": "crate"}
Usage (file):  python run_headless.py build_prop.py name=crate spec=parts.json
Args: name (collection and prefix, "prop"), spec (path to JSON list of parts, or omit for the demo crate),
      max_ngons (int, 0).
A part: {"kind": "box"|"cylinder"|"bolt", "name": "lid", "size": [x,y,z] | "radius","depth","sides","bevel",
         "loc": [x,y,z], "rot": [rx,ry,rz], "holes": [[u,v,r],...], "material": "mat name"}.
Sizes in metres. Prints one GAUGE_JSON line, gate "build-prop", with the mesh-health checks included.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge
import kit

P = gauge.params(globals(), name="prop", spec=None, max_ngons=0)

DEMO = [
    {"kind": "box", "name": "body", "size": [0.9, 0.6, 0.45], "bevel": 0.018, "loc": [0, 0, 0.225]},
    {"kind": "box", "name": "lid", "size": [0.94, 0.64, 0.05], "bevel": 0.014, "loc": [0, 0, 0.475]},
    {"kind": "box", "name": "strap_a", "size": [0.07, 0.66, 0.52], "bevel": 0.008, "loc": [-0.28, 0, 0.26]},
    {"kind": "box", "name": "strap_b", "size": [0.07, 0.66, 0.52], "bevel": 0.008, "loc": [0.28, 0, 0.26]},
    {"kind": "box", "name": "plate", "size": [0.3, 0.012, 0.18], "bevel": 0.003, "loc": [0, -0.322, 0.26],
     "holes": [[-0.11, 0, 0.012], [0.11, 0, 0.012]]},
] + [{"kind": "bolt", "name": f"bolt_{i}", "radius": 0.013, "loc": [x, -0.34, z], "rot": [1.5708, 0, 0]}
     for i, (x, z) in enumerate([(-0.28, 0.12), (0.28, 0.12), (-0.28, 0.38), (0.28, 0.38)])]

spec = DEMO
if P["spec"]:
    with open(P["spec"]) as fh:
        spec = json.load(fh)

old = bpy.data.collections.get(P["name"])
if old:
    gauge.workspace_remove(P["name"], confirm=True)
col = gauge.workspace_make(P["name"])
made = []
for part in spec:
    kind, nm = part["kind"], f'{P["name"]}_{part["name"]}'
    loc, rot = tuple(part.get("loc", (0, 0, 0))), tuple(part.get("rot", (0, 0, 0)))
    if kind == "box":
        ob = kit.rounded_box(nm, tuple(part["size"]), part.get("bevel", 0.01), part.get("segments", 3), loc, rot, col)
    elif kind == "cylinder":
        ob = kit.cylinder(nm, part.get("radius", 0.1), part.get("depth", 0.2), part.get("sides", 32),
                          part.get("bevel", 0.0), 2, loc, rot, col)
    elif kind == "bolt":
        ob = kit.bolt_head(nm, part.get("radius", 0.012), part.get("height", 0.008), part.get("sides", 6),
                           part.get("bevel", 0.0015), loc, rot, col)
    else:
        raise ValueError(f"unknown part kind '{kind}'")
    if part.get("holes"):
        kit.cut_holes(ob, [tuple(h) for h in part["holes"]])
    if part.get("material"):
        kit.assign(ob, part["material"])
    made.append(ob)

r = gauge.Report("build-prop")
r.info["parts"] = [o.name for o in made]
r.info["size_m"] = [round(v, 3) for v in gauge.size_of(made)]
gauge.mesh_gate(r, made, max_ngons=P["max_ngons"], per_object=False)
r.emit()
