"""Gate a Geometry Nodes result: valid tree, non-empty output, instance count, size, smoothness of a grid.

Usage (live):  run_blender_script path=skills/gauge-geonodes/scripts/gn_gate.py
               args={"object": "Terrain", "min_instances": 1000, "max_neighbour_step": 0.08}
Args: object (host with a Geometry Nodes modifier; default every object that has one), min_instances, max_instances,
      max_size ([x, y, z] metres, bounding box of the evaluated object), max_neighbour_step (metres; for instances on an
      XY grid, the largest height jump between neighbours), max_faces (realised mesh budget).
Prints one GAUGE_JSON line, gate "geonodes-health". Instances are counted from the evaluated depsgraph, so hiding
the source object does not change the count.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge

P = gauge.params(globals(), object=None, min_instances=None, max_instances=None, max_size=None,
                 max_neighbour_step=None, max_faces=None)
r = gauge.Report("geonodes-health")
hosts = ([bpy.data.objects[P["object"]]] if P["object"] and P["object"] in bpy.data.objects else [] if P["object"] else
         [o for o in bpy.context.scene.objects if any(m.type == "NODES" for m in o.modifiers)])
r.check("hosts_found", [h.name for h in hosts], len(hosts) > 0, "> 0", "no object with a Geometry Nodes modifier")
for h in hosts:
    for m in h.modifiers:
        if m.type == "NODES" and m.node_group:
            gauge.node_gate(r, m.node_group, m.node_group.name)
    n = gauge.instance_count(h)
    st = gauge.mesh_stats(h, uv_checks=False)
    r.check(f"{h.name}: not_empty", n + st["faces"], n + st["faces"] > 0, "> 0", "evaluates to nothing")
    r.info.setdefault("objects", {})[h.name] = {"instances": n, "faces": st["faces"], "size_m": [round(v, 3) for v in gauge.size_of([h])]}
    if P["min_instances"] is not None:
        r.ge(f"{h.name}: instances_min", n, P["min_instances"])
    if P["max_instances"] is not None:
        r.le(f"{h.name}: instances_max", n, P["max_instances"], hint="lower the resolution or the density")
    if P["max_faces"] is not None:
        r.le(f"{h.name}: realised_faces", st["faces"], P["max_faces"])
    if P["max_size"]:
        sz = gauge.size_of([h])
        for axis, v, lim in zip("xyz", sz, P["max_size"]):
            r.le(f"{h.name}: size_{axis}", v, lim)
    if P["max_neighbour_step"] is not None and n:
        gs = gauge.grid_step(gauge.instance_positions(h))
        r.info["objects"][h.name]["grid"] = gs
        r.le(f"{h.name}: neighbour_step", gs["max_step"], P["max_neighbour_step"],
             hint="noise too rough between neighbours: lower Roughness, narrow Map Range, or raise Noise Scale")
r.emit()
