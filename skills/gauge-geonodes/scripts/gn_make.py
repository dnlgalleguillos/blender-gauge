"""Build a Geometry Nodes group from a recipe (or any spec file) and attach it to a host object.

Usage (live):  run_blender_script path=skills/gauge-geonodes/scripts/gn_make.py
               args={"recipe": "height_grid", "host": "Terrain", "inputs": {"Amplitude": 0.4, "Res X": 80}}
Usage (file):  python run_headless.py gn_make.py recipe=radial_array host=Ring inputs='{"Count": 16}'
Args: recipe (name of a file in ../recipes, or a path to a spec JSON), group (node group name, default = recipe),
      host (object that gets the modifier; created as an empty-mesh object if missing), inputs (dict by input name),
      collection (where new objects go, default the active collection).
Object inputs left empty ("Source", "Instance", "Target") are filled with a small generated mesh; the instance
source is hidden in the viewport and render but keeps producing instances. Prints one GAUGE_JSON line, gate
"geonodes-make", with the instance count and size of the result. Rebuilding replaces the group and keeps the host.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge

HERE = os.path.dirname(os.path.abspath(__file__))
P = gauge.params(globals(), recipe="height_grid", group=None, host=None, inputs={}, collection=None)
path = P["recipe"] if os.path.exists(P["recipe"]) else os.path.join(HERE, "..", "recipes", P["recipe"] + ".json")
with open(path) as fh:
    spec = json.load(fh)
gname = P["group"] or os.path.splitext(os.path.basename(path))[0]
col = bpy.data.collections.get(P["collection"]) if P["collection"] else bpy.context.view_layer.active_layer_collection.collection

if bpy.data.objects.get(P["host"] or gname + "_host") is None:
    me = bpy.data.meshes.new((P["host"] or gname + "_host"))
    host = bpy.data.objects.new(P["host"] or gname + "_host", me)
    col.objects.link(host)
else:
    host = bpy.data.objects[P["host"] or gname + "_host"]

group = gauge.gn_make(gname, spec)
mod = host.modifiers.get(gname) or host.modifiers.new(gname, "NODES")
mod.node_group = group

values = dict(P["inputs"] or {})
made = []
for item in spec["interface"]["inputs"]:
    if item["type"] == "Object" and item["name"] not in values:
        import bmesh
        nm = f"{gname}_{item['name'].lower()}"
        obj = bpy.data.objects.get(nm)
        if obj is None:
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            if item["name"] == "Target":
                bmesh.ops.create_grid(bm, x_segments=4, y_segments=4, size=2.0)
            me2 = bpy.data.meshes.new(nm)
            bm.to_mesh(me2)
            bm.free()
            obj = bpy.data.objects.new(nm, me2)
            col.objects.link(obj)
            if item["name"] != "Target":
                obj.hide_render = True
                obj.hide_set(True)
            made.append(nm)
        values[item["name"]] = obj.name
gauge.gn_set(mod, **values)
bpy.context.view_layer.update()

r = gauge.Report("geonodes-make")
gauge.node_gate(r, group, gname)
n = gauge.instance_count(host)
r.check("produces_geometry", n, n > 0 or gauge.mesh_stats(host)["faces"] > 0, "> 0 instances or faces",
        "the group output is empty: check the links into Group Output and the object inputs")
r.info.update(group=gname, host=host.name, instances=n, created=made, size_m=[round(v, 3) for v in gauge.size_of([host])],
              inputs=gauge.gn_inputs(group))
r.emit()
