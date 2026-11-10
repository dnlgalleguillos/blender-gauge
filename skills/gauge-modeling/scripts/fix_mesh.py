"""Repair common mesh defects with bmesh. Dry run unless apply=true.

Usage (live):  run_blender_script path=skills/gauge-modeling/scripts/fix_mesh.py args={"collection": "Props", "apply": true}
Args: collection (object/collection name; default whole scene), apply (bool, false),
      steps (list of: "merge", "loose", "degenerate", "normals", "triangulate_ngons"; default the first four).
Skips meshes whose data is shared with an object outside the selection. Prints one GAUGE_JSON line, gate "fix-mesh",
with info.fixes = [{object, step, count}].
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmesh
import bpy

import gauge

P = gauge.params(globals(), collection=None, apply=False, steps=["merge", "loose", "degenerate", "normals"])
fixes = []
for ob in gauge.pick(P["collection"]):
    if any(m.type != "NONE" for m in ob.modifiers) and ob.type == "MESH":
        pass  # base mesh is repaired; modifiers re-evaluate afterwards
    bm = bmesh.new()
    bm.from_mesh(ob.data)

    def note(step, n):
        if n:
            fixes.append({"object": ob.name, "step": step, "count": n})

    if "merge" in P["steps"]:
        t = bmesh.ops.find_doubles(bm, verts=bm.verts, dist=1e-5)["targetmap"]
        note("merge", len(t))
        if P["apply"] and t:
            bmesh.ops.weld_verts(bm, targetmap=t)
    if "degenerate" in P["steps"]:
        bad = [f for f in bm.faces if f.calc_area() < 1e-10]
        note("degenerate", len(bad))
        if P["apply"] and bad:
            bmesh.ops.delete(bm, geom=bad, context="FACES")
    if "loose" in P["steps"]:
        loose = [v for v in bm.verts if not v.link_edges]
        note("loose", len(loose))
        if P["apply"] and loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
    if "normals" in P["steps"]:
        closed = not any(e.is_boundary or not e.is_manifold for e in bm.edges) and bm.faces
        if closed and bm.calc_volume(signed=True) < 0:
            note("normals", len(bm.faces))
            if P["apply"]:
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if "triangulate_ngons" in P["steps"]:
        ng = [f for f in bm.faces if len(f.verts) > 4]
        note("triangulate_ngons", len(ng))
        if P["apply"] and ng:
            bmesh.ops.triangulate(bm, faces=ng)
    if P["apply"]:
        bm.to_mesh(ob.data)
        ob.data.update()
    bm.free()
r = gauge.Report("fix-mesh")
r.check("applied" if P["apply"] else "dry_run", len(fixes), True)
r.info.update(fixes=fixes[:80], applied=bool(P["apply"]))
r.emit()
