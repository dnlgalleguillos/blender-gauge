"""Export objects to glTF/GLB, FBX, OBJ, STL, USD or PLY, then verify the file by importing it back into a scratch scene.

Usage (live):  run_blender_script path=skills/gauge-export/scripts/export.py args={"out": "/tmp/crate.glb", "objects": "crate"}
Usage (file):  python run_headless.py export.py --blend asset.blend out=/tmp/asset.glb objects=Props budget=web
Args: out (path; the extension picks the format: .glb .gltf .fbx .obj .stl .usd .usda .usdc .ply),
      objects (object/collection name or list; default every visible mesh), apply_modifiers (bool, true),
      budget (web | mobile | desktop | none; sets limits below), max_tris, max_texture_px, max_objects (override the budget),
      verify (bool, true: re-import and compare), tolerance (relative size tolerance, 0.01).
Budgets: web 100k tris / 2048 px, mobile 30k / 1024, desktop 500k / 4096.
Round-trip checks: the file exists and is non-empty, triangles match, the sorted bounding-box dimensions match within
`tolerance` (axis conventions differ between formats, so dimensions are compared sorted), materials survive (formats that
carry them), and nothing the import created is left in the session. glTF is written without mesh compression.
Prints one GAUGE_JSON line, gate "export".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge

P = gauge.params(globals(), out="/tmp/gauge_export.glb", objects=None, apply_modifiers=True, budget="none",
                 max_tris=None, max_texture_px=None, max_objects=None, verify=True, tolerance=0.01)
BUDGETS = {"web": (100_000, 2048), "mobile": (30_000, 1024), "desktop": (500_000, 4096), "none": (None, None)}
if P["budget"] not in BUDGETS:
    raise KeyError(f"unknown budget '{P['budget']}' (have: {sorted(BUDGETS)})")
max_tris = P["max_tris"] if P["max_tris"] is not None else BUDGETS[P["budget"]][0]
max_tex = P["max_texture_px"] if P["max_texture_px"] is not None else BUDGETS[P["budget"]][1]
out = os.path.abspath(P["out"])
ext = os.path.splitext(out)[1].lower()
os.makedirs(os.path.dirname(out), exist_ok=True)

EXPORT = {
    ".glb": lambda sel: bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=sel, export_apply=P["apply_modifiers"]),
    ".gltf": lambda sel: bpy.ops.export_scene.gltf(filepath=out, export_format="GLTF_SEPARATE", use_selection=sel, export_apply=P["apply_modifiers"]),
    ".fbx": lambda sel: bpy.ops.export_scene.fbx(filepath=out, use_selection=sel, use_mesh_modifiers=P["apply_modifiers"]),
    ".obj": lambda sel: bpy.ops.wm.obj_export(filepath=out, export_selected_objects=sel, apply_modifiers=P["apply_modifiers"]),
    ".stl": lambda sel: bpy.ops.wm.stl_export(filepath=out, export_selected_objects=sel, apply_modifiers=P["apply_modifiers"]),
    ".usd": lambda sel: bpy.ops.wm.usd_export(filepath=out, selected_objects_only=sel),
    ".usda": lambda sel: bpy.ops.wm.usd_export(filepath=out, selected_objects_only=sel),
    ".usdc": lambda sel: bpy.ops.wm.usd_export(filepath=out, selected_objects_only=sel),
    ".ply": lambda sel: bpy.ops.wm.ply_export(filepath=out, export_selected_objects=sel, apply_modifiers=P["apply_modifiers"]),
}
IMPORT = {
    ".glb": lambda: bpy.ops.import_scene.gltf(filepath=out), ".gltf": lambda: bpy.ops.import_scene.gltf(filepath=out),
    ".fbx": lambda: bpy.ops.import_scene.fbx(filepath=out), ".obj": lambda: bpy.ops.wm.obj_import(filepath=out),
    ".stl": lambda: bpy.ops.wm.stl_import(filepath=out), ".usd": lambda: bpy.ops.wm.usd_import(filepath=out),
    ".usda": lambda: bpy.ops.wm.usd_import(filepath=out), ".usdc": lambda: bpy.ops.wm.usd_import(filepath=out),
    ".ply": lambda: bpy.ops.wm.ply_import(filepath=out),
}
CARRIES_MATERIALS = {".glb", ".gltf", ".fbx", ".usd", ".usda", ".usdc", ".obj"}

def main():
    r = gauge.Report("export")
    if not r.check("format_known", ext, ext in EXPORT, "one of " + " ".join(sorted(EXPORT))):
        r.emit()
        return
    objs = gauge.pick(P["objects"])
    if not r.check("objects_found", len(objs), len(objs) > 0, "> 0", "nothing to export: check the name"):
        r.emit()
        return
    src_dims = sorted(gauge.size_of(objs))
    src_tris = sum(gauge.mesh_stats(o, uv_checks=False).get("triangles", 0) for o in objs)
    src_mats = len({s.material.name for o in objs for s in o.material_slots if s.material})
    if max_tris is not None:
        r.le("triangles_budget", src_tris, max_tris, hint="decimate or lower subdivision/bevel segments")
    if P["max_objects"] is not None:
        r.le("object_count_budget", len(objs), P["max_objects"], hint="join parts that share a material")
    if max_tex is not None:
        big = sorted({f"{i.name} {i.size[0]}x{i.size[1]}" for o in objs for s in o.material_slots if s.material and s.material.node_tree
                      for n in s.material.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage" and (i := n.image) is not None
                      and max(i.size) > max_tex})
        r.check("texture_size_budget", big[:6], not big, f"<= {max_tex}px", "downscale the texture before export")

    prev_sel = [(o, o.select_get()) for o in bpy.context.view_layer.objects]
    prev_active = bpy.context.view_layer.objects.active

    def restore_selection():  # exporters and importers both change the selection: put it back
        for o, was in prev_sel:
            try:
                o.select_set(was)
            except (RuntimeError, ReferenceError):
                pass
        try:
            bpy.context.view_layer.objects.active = prev_active
        except (RuntimeError, ReferenceError):
            pass

    try:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        if objs:
            bpy.context.view_layer.objects.active = objs[0]
        res = EXPORT[ext](True)
    finally:
        restore_selection()
    exists = os.path.exists(out) and os.path.getsize(out) > 0
    r.check("file_written", out, exists, "non-empty file", "exporter produced nothing: " + str(res))
    r.info.update(out=out, bytes=os.path.getsize(out) if exists else 0, objects=len(objs), triangles=src_tris,
                  size_m=[round(v, 3) for v in gauge.size_of(objs)])

    if P["verify"] and exists:
        colls = ("objects", "meshes", "materials", "images", "cameras", "lights", "collections")
        before = {c: set(getattr(bpy.data, c).keys()) for c in colls}
        IMPORT[ext]()
        new_objs = [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before["objects"]]
        meshes = [o for o in new_objs if o.type == "MESH"]
        try:
            got_tris = sum(gauge.mesh_stats(o, uv_checks=False).get("triangles", 0) for o in meshes)
            r.eq("roundtrip_triangles", got_tris, src_tris, hint="the exporter changed the triangle count")
            dims = sorted(gauge.size_of(meshes))
            worst = max((abs(a - b) / max(a, 1e-9) for a, b in zip(dims, src_dims) if a > 1e-6), default=0.0)
            r.le("roundtrip_size_error", round(worst, 5), P["tolerance"], hint="scale or unit mismatch between Blender and the format")
            if ext in CARRIES_MATERIALS:
                got_mats = len({s.material.name for o in meshes for s in o.material_slots if s.material})
                r.ge("roundtrip_materials", got_mats, min(src_mats, 1) if src_mats else 0, hint="materials were dropped")
            r.info["roundtrip"] = {"triangles": got_tris, "size_m": [round(v, 3) for v in dims], "materials_src": src_mats}
        finally:
            for o in new_objs:
                bpy.data.objects.remove(o, do_unlink=True)
            for c in colls[1:]:
                coll = getattr(bpy.data, c)
                for n in [n for n in coll.keys() if n not in before[c]]:
                    try:
                        coll.remove(coll[n])
                    except (RuntimeError, ReferenceError):
                        pass
        left = [c for c in colls if set(getattr(bpy.data, c).keys()) - before[c]]
        r.check("import_cleaned_up", left, not left, "nothing left behind", "scratch import left datablocks in the session")
        restore_selection()
    r.emit()


main()
