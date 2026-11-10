"""Print any node tree as text: material, world, Geometry Nodes group, or compositor (headless twin of MCP get_node_tree).

Usage:  run_blender_script path=skills/gauge-reference/scripts/node_text.py args={"material": "mat_steel"}
Args: material | group | world (a name), scene (true: the compositor tree of the scene), spec (path: also write the
      JSON spec you can rebuild with gauge.node_build / gauge.gn_make).
Output lists nodes in data-flow order with only the values that differ from a fresh node, then each node's incoming
links. Prints one GAUGE_JSON line, gate "node-text".
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge

P = gauge.params(globals(), material=None, group=None, world=None, scene=False, spec=None)
r = gauge.Report("node-text")
tree = None
if P["material"]:
    m = bpy.data.materials.get(P["material"])
    tree = m.node_tree if m else None
    r.check("material_exists", P["material"], m is not None, "exists", f"materials: {[x.name for x in bpy.data.materials][:15]}")
elif P["group"]:
    tree = bpy.data.node_groups.get(P["group"])
    r.check("group_exists", P["group"], tree is not None, "exists", f"groups: {[x.name for x in bpy.data.node_groups][:15]}")
elif P["world"]:
    w = bpy.data.worlds.get(P["world"])
    tree = w.node_tree if w else None
    r.check("world_exists", P["world"], w is not None, "exists")
elif P["scene"]:
    tree = bpy.context.scene.compositing_node_group
    r.check("compositor_tree_exists", bool(tree), tree is not None, True, "this scene has no compositor tree")
if tree is not None:
    print(gauge.node_text(tree))
    if P["spec"]:
        with open(P["spec"], "w") as fh:
            json.dump(gauge.node_dump(tree), fh, indent=1)
        r.info["written"] = P["spec"]
    r.info["nodes"] = len(tree.nodes)
r.emit()
