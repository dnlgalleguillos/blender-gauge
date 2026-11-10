"""Build a lighting rig sized to the subject, measure its ratios, optionally add a ground and set the world.

Usage (live):  run_blender_script path=skills/gauge-light-render/scripts/rig.py args={"subject": "Props", "preset": "three_point"}
Usage (file):  python run_headless.py rig.py --blend scene.blend subject=Props preset=softbox_product
Args: subject (object or collection to light; default the whole scene's meshes), preset (three_point, softbox_product,
      dramatic, overcast), strength (multiplier on every light, 1.0), ground (bool, false: add a floor under the
      subject), ground_color (sRGB hex of that floor, #3a3c42), world_color (hex, optional), azimuth (deg, 0 = lights relative to a camera in front on -Y, 0).
Distances, sizes and powers scale with the subject radius R, so the same preset works for a ring or a building.
Lights go into collection "gauge_rig" (rebuilt on every run) and are invisible to the camera.
Prints one GAUGE_JSON line, gate "light-rig", with info.ratio_key_fill (irradiance at the subject) and per-light data.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmesh
import bpy
from mathutils import Vector

import gauge

P = gauge.params(globals(), subject=None, preset="three_point", strength=1.0, ground=False, ground_color="#3a3c42",
                 world_color=None, azimuth=0.0)

# (name, azimuth deg, elevation deg, distance in R, irradiance W/m2 at the subject, size in R, size_y in R or None)
PRESETS = {
    "three_point": {"world": ("#0d0e12", 0.8), "lights": [
        ("key", -40, 38, 3.4, 16.0, 2.0, None), ("fill", 55, 14, 4.2, 4.0, 3.0, None), ("rim", 160, 32, 3.8, 22.0, 1.0, 2.2)]},
    "softbox_product": {"world": ("#101115", 0.6), "lights": [
        ("top", 0, 82, 3.0, 20.0, 3.6, 3.6), ("strip_l", -78, 18, 3.4, 22.0, 0.7, 3.0), ("strip_r", 78, 18, 3.4, 22.0, 0.7, 3.0)]},
    "dramatic": {"world": ("#050507", 0.3), "lights": [
        ("key", -62, 24, 3.2, 38.0, 0.5, None), ("rim", 150, 28, 3.8, 18.0, 0.8, 2.0), ("kick", 70, 6, 4.5, 2.5, 2.0, None)]},
    "overcast": {"world": ("#8a96a6", 1.0), "lights": [("sky", 0, 85, 4.0, 5.0, 6.0, 6.0)]},
}
if P["preset"] not in PRESETS:
    raise KeyError(f"unknown preset '{P['preset']}' (have: {sorted(PRESETS)})")
sc = bpy.context.scene
subject = gauge.pick(P["subject"])
b = gauge.bounds(subject)
if b is None:
    raise RuntimeError("nothing to light: subject has no geometry")
lo, hi = b
centre = (lo + hi) / 2
R = max((hi - lo).length / 2, 0.05)

gauge.workspace_remove("gauge_rig", confirm=True)
col = gauge.workspace_make("gauge_rig")
az0 = math.radians(P["azimuth"])
infos = []
for name, az, el, dist, irr, size, size_y in PRESETS[P["preset"]]["lights"]:
    a, e, d = math.radians(az) + az0, math.radians(el), dist * R
    pos = centre + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * d
    ld = bpy.data.lights.new(f"rig_{name}", "AREA")
    ld.shape = "RECTANGLE" if size_y else "SQUARE"
    ld.size = size * R
    if size_y:
        ld.size_y = size_y * R
    ld.energy = irr * P["strength"] * math.pi * d * d * 0.5  # irradiance at the subject -> watts: grows with distance squared
    ob = bpy.data.objects.new(f"rig_{name}", ld)
    ob.location = pos
    ob.rotation_euler = (centre - pos).to_track_quat("-Z", "Y").to_euler()
    ob.visible_camera = False
    col.objects.link(ob)
    infos.append({"light": ob.name, "watts": round(ld.energy, 1), "distance_m": round(d, 3), "irradiance": round(irr * P["strength"], 2)})

wcol, wstr = PRESETS[P["preset"]]["world"]
if P["world_color"]:
    wcol = P["world_color"]
world = bpy.data.worlds.get("gauge_world") or bpy.data.worlds.new("gauge_world")
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (*gauge.hex_to_linear(wcol), 1.0)
bg.inputs["Strength"].default_value = wstr
sc.world = world

if P["ground"]:
    old = bpy.data.objects.get("rig_ground")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=R * 40)
    me = bpy.data.meshes.new("rig_ground")
    bm.to_mesh(me)
    bm.free()
    g = bpy.data.objects.new("rig_ground", me)
    g.location = (centre.x, centre.y, lo.z)
    mat = bpy.data.materials.get("rig_ground_mat") or bpy.data.materials.new("rig_ground_mat")
    pb = mat.node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = (*gauge.hex_to_linear(P["ground_color"]), 1)
    pb.inputs["Roughness"].default_value = 0.65
    me.materials.append(mat)
    col.objects.link(g)

key = infos[0]["irradiance"]
fills = [i["irradiance"] for i in infos[1:] if "fill" in i["light"] or "kick" in i["light"] or "strip" in i["light"]]
r = gauge.Report("light-rig")
r.check("lights_created", len(infos), len(infos) >= 1, ">= 1")
r.check("none_visible_to_camera", [o.name for o in col.objects if o.type == "LIGHT" and o.visible_camera], not any(
    o.visible_camera for o in col.objects if o.type == "LIGHT"), "none")
if fills:
    ratio = key / max(fills)
    r.info["ratio_key_fill"] = round(ratio, 2)
    r.check("key_to_fill_ratio", round(ratio, 2), 0.8 <= ratio <= 12.0, "0.8 .. 12", "ratio outside a usable range", severity="warn")
r.info.update(subject_radius_m=round(R, 3), centre=[round(v, 3) for v in centre], lights=infos, preset=P["preset"])
r.emit()
