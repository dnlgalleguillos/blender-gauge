"""Render a sheet of material swatches (one sphere per preset) on a neutral studio, then measure it.

Usage (headless, preferred):  python run_headless.py swatch_sheet.py out=/tmp/swatches.png
Usage (live, small only):     run_blender_script path=skills/gauge-materials/scripts/swatch_sheet.py args={"out": "/tmp/s.png", "percent": 40}
Args: out (png path), presets (list; default all), color (hex applied to every preset that takes one, optional),
      samples (int, 48), width/height (px, 1600x800), percent (resolution %, 100), build_only (bool, false).
Renders in its own temporary scene, so nothing from the open scene appears in the sheet; the scene is removed afterwards unless keep=true. Gate "swatch-sheet":
every swatch must differ from its neighbours (no preset renders identically) and the image must pass exposure.
Prints one GAUGE_JSON line.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmesh
import bpy
from mathutils import Vector

import gauge
import presets

P = gauge.params(globals(), out="/tmp/gauge_swatches.png", presets=None, color=None, samples=48, width=1600,
                 height=800, percent=100, keep=False, build_only=False)
names = P["presets"] or list(presets.PRESETS)
main = bpy.context.scene
sc = bpy.data.scenes.new("gauge_swatch_scene")  # isolated: nothing from the user's scene can leak into the sheet
col = bpy.data.collections.new("gauge_swatches")
sc.collection.children.link(col)
objs = []
cols = min(5, len(names))
rows = math.ceil(len(names) / cols)
gap = 1.25
for i, nm in enumerate(names):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=0.5)
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(f"sw_{nm}")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(f"swatch_{nm}", me)
    cy = i // cols
    in_row = min(cols, len(names) - cy * cols)  # rows are centred, so a shorter back row sits between the front spheres
    cx = i % cols
    ob.location = ((cx - (in_row - 1) / 2) * gap, cy * gap * 0.9, 0.5)
    col.objects.link(ob)
    me.materials.append(presets.make(f"sw_{nm}", nm, P["color"] if nm in ("metal", "brushed_metal", "plastic", "ceramic", "rubber") else None))
    objs.append(ob)
floor = bpy.data.objects.new("swatch_floor", bpy.data.meshes.new("swatch_floor"))
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=14.0)
bm.to_mesh(floor.data)
bm.free()
fm = bpy.data.materials.get("sw_floor") or bpy.data.materials.new("sw_floor")
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.18, 0.18, 0.19, 1)
fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
floor.data.materials.append(fm)
col.objects.link(floor)
mid_y = (rows - 1) * gap * 0.9 / 2
focus = Vector((0, mid_y, 0.45))
key = bpy.data.objects.new("swatch_key", bpy.data.lights.new("swatch_key", "AREA"))
key.data.energy, key.data.size = 520.0, 4.0
key.location = (-3.5, mid_y - 3.0, 5.0)
fill = bpy.data.objects.new("swatch_fill", bpy.data.lights.new("swatch_fill", "AREA"))
fill.data.energy, fill.data.size = 140.0, 5.0
fill.location = (5.0, mid_y - 3.5, 2.6)
for lt in (key, fill):
    lt.rotation_euler = (focus - lt.location).to_track_quat("-Z", "Y").to_euler()
    lt.visible_camera = False
    col.objects.link(lt)
cam = bpy.data.objects.new("swatch_cam", bpy.data.cameras.new("swatch_cam"))
cam.data.lens = 65
tan_h = (cam.data.sensor_width / 2) / cam.data.lens
dist = ((cols - 1) * gap + 1.4) / 2 / (tan_h * 0.9)
el = math.radians(24)
cam.location = focus + Vector((0, -math.cos(el), math.sin(el))) * dist
cam.rotation_euler = (focus - cam.location).to_track_quat("-Z", "Y").to_euler()
col.objects.link(cam)
sc.camera = cam
world = bpy.data.worlds.get("swatch_world") or bpy.data.worlds.new("swatch_world")
nt = world.node_tree
nt.nodes["Background"].inputs["Color"].default_value = (0.09, 0.095, 0.11, 1)
nt.nodes["Background"].inputs["Strength"].default_value = 0.6
sc.world = world
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.render.film_transparent = False
sc.render.resolution_x, sc.render.resolution_y = P["width"], P["height"]
try:
    sc.view_settings.view_transform = "AgX"
except TypeError:
    pass
r = gauge.Report("swatch-sheet")
for o in col.objects:  # the temporary scene is not active, so its matrices are not evaluated: set them directly
    o.matrix_world = o.matrix_basis.copy()
for ob in objs:
    hid = gauge.occluded_by(cam.matrix_world.translation, ob, objs + [floor])
    r.check(f"{ob.name}: not_occluded", hid, not hid, "none", "something stands between the camera and the swatch")
r.info["presets"] = names
gauge.lights_gate(r, sc)
if not P["build_only"]:
    path = gauge.render(P["out"], samples=P["samples"], percent=P["percent"], scene=sc)
    a = gauge.load_pixels(path)
    st = gauge.exposure_gate(r, path, max_clip_white=0.03, min_contrast=0.2)
    H, W = a.shape[:2]
    from numpy import abs as nabs
    means = []
    for i, ob in enumerate(objs):
        f = gauge.framing(sc, cam, [ob])
        x0, y0, x1, y1 = f["bbox"]
        cx = int((x0 + x1) / 2 * W)
        cy = int((1 - (y0 + y1) / 2) * H)
        patch = a[max(0, cy - 4):cy + 4, max(0, cx - 4):cx + 4, :3]
        means.append(patch.reshape(-1, 3).mean(0))
        r.check(f"{ob.name}: inside_frame", f["margin"], f["margin"] >= 0, ">= 0", "swatch cropped by the camera")
    dists = [float(nabs(means[i] - means[j]).sum()) for i in range(len(means)) for j in range(i + 1, len(means))]
    r.ge("swatches_distinct_min_distance", min(dists) if dists else 1.0, 0.004,
         hint="two presets render the same at the sample point; check the preset parameters")
    r.info["out"] = path
if not P["keep"]:
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(col)
    bpy.data.scenes.remove(sc)
    for lt in [x for x in bpy.data.lights if x.name.startswith("swatch_")]:
        bpy.data.lights.remove(lt)
    for cm in [x for x in bpy.data.cameras if x.name.startswith("swatch_")]:
        bpy.data.cameras.remove(cm)
    for me in [x for x in bpy.data.meshes if x.users == 0 and (x.name.startswith("sw_") or x.name == "swatch_floor")]:
        bpy.data.meshes.remove(me)
r.emit()
