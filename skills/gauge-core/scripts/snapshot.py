"""Snapshot of the open scene: counts, hygiene gate, render setup. Run this first, before touching anything.

Usage (live):  run_blender_script path=skills/gauge-core/scripts/snapshot.py
Usage (file):  python run_headless.py snapshot.py --blend scene.blend
Args: max_ngons (int, optional)  fail when the scene has more n-gons than this.
Prints one GAUGE_JSON line: gate "snapshot" with scene counts under info.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import gauge

P = gauge.params(globals(), max_ngons=None)
r = gauge.Report("snapshot")
sc = bpy.context.scene
gauge.scene_gate(r, sc)
meshes = gauge.pick(None)
gauge.mesh_gate(r, meshes, max_ngons=P["max_ngons"], per_object=False)
kinds = {}
for o in sc.objects:
    kinds[o.type] = kinds.get(o.type, 0) + 1
r.info["objects_by_type"] = kinds
r.info["collections"] = [c.name for c in bpy.data.collections]
r.info["render"] = {"engine": sc.render.engine, "resolution": [sc.render.resolution_x, sc.render.resolution_y,
                    sc.render.resolution_percentage], "view_transform": sc.view_settings.view_transform,
                    "look": sc.view_settings.look}
r.info["blender"] = bpy.app.version_string
r.info["file"] = bpy.data.filepath or "(unsaved)"
r.info["size_m"] = [round(v, 3) for v in gauge.size_of(meshes)]
r.emit()
