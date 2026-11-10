"""Read a Geometry Nodes group (or any material) back as a spec you can edit and rebuild.

Usage (live):  run_blender_script path=skills/gauge-geonodes/scripts/gn_dump.py args={"group": "height_grid", "out": "/tmp/spec.json"}
Args: group (node group name), out (JSON path; omit to print the readable text), text (bool: also print node_text).
Prints the readable data-flow text (or writes the spec) and one GAUGE_JSON line, gate "gn-dump".
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge

P = gauge.params(globals(), group=None, out=None, text=True)
def main():
    r = gauge.Report("gn-dump")
    g = bpy.data.node_groups.get(P["group"])
    if not r.check("group_exists", P["group"], g is not None, "exists", f"groups: {[x.name for x in bpy.data.node_groups]}"):
        r.emit()
        return
    spec = gauge.node_dump(g)
    spec["interface"] = {"inputs": [{"name": i.name, "type": next((k for k, v in gauge._SOCKET_TYPES.items() if v == i.socket_type), i.socket_type)}
                                    for i in g.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"],
                         "outputs": [{"name": i.name, "type": next((k for k, v in gauge._SOCKET_TYPES.items() if v == i.socket_type), i.socket_type)}
                                     for i in g.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "OUTPUT"]}
    if P["out"]:
        with open(P["out"], "w") as fh:
            json.dump(spec, fh, indent=1)
        r.info["written"] = P["out"]
    if P["text"] or not P["out"]:
        print(gauge.node_text(g))
    r.info["nodes"] = len(spec["nodes"])
    r.emit()


main()
