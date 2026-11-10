"""Add a turntable: a pivot at the subject's centre that turns 360 degrees with the camera parented to it.

Usage (live):  run_blender_script path=skills/gauge-light-render/scripts/turntable.py args={"subject": "Props", "frames": 120}
Args: subject, frames (120), fps (24), pivot (name, "gauge_pivot"), camera (existing camera to orbit; default the scene camera).
Linear interpolation, last frame is one step before a full turn so the loop has no stutter. Prints one GAUGE_JSON line,
gate "turntable", after checking the angle at the first and last frame and at frame_end + 1 (must equal the first).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Matrix

import gauge

P = gauge.params(globals(), subject=None, frames=120, fps=24, pivot="gauge_pivot", camera=None)
sc = bpy.context.scene
objs = gauge.pick(P["subject"])
lo, hi = gauge.bounds(objs)
centre = (lo + hi) / 2
cam = bpy.data.objects[P["camera"]] if P["camera"] else sc.camera
if cam is None:
    raise RuntimeError("no camera: run frame_camera.py first")
piv = bpy.data.objects.get(P["pivot"])
if piv is None:
    piv = bpy.data.objects.new(P["pivot"], None)
    bpy.context.view_layer.active_layer_collection.collection.objects.link(piv)
piv.location = centre
piv.rotation_euler = (0, 0, 0)
piv.animation_data_clear()
bpy.context.view_layer.update()
world = cam.matrix_world.copy()
cam.parent = piv
cam.matrix_parent_inverse = piv.matrix_world.inverted()
cam.matrix_world = world
start, n = 1, int(P["frames"])
sc.frame_start, sc.frame_end, sc.render.fps = start, start + n - 1, int(P["fps"])
piv.rotation_euler.z = 0.0
piv.keyframe_insert("rotation_euler", index=2, frame=start)
piv.rotation_euler.z = 2 * math.pi
piv.keyframe_insert("rotation_euler", index=2, frame=start + n)
for fc in gauge.fcurves_of(piv.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"  # constant speed (the default Bezier eases in and out)
    fc.update()


def angle_at(frame):
    sc.frame_set(frame)
    return piv.rotation_euler.z


r = gauge.Report("turntable")
a0, a1, a2 = angle_at(start), angle_at(sc.frame_end), angle_at(start + n)
a_q = angle_at(start + n // 4)
r.eq("first_frame_angle", a0, 0.0, 1e-4)
r.check("constant_speed", round(a_q, 4), abs(a_q - 2 * math.pi * (n // 4) / n) < 1e-2, f"~{2 * math.pi * (n // 4) / n:.3f}",
        "keyframes are not linear: the turn would ease in and out")
r.check("last_frame_before_full_turn", round(a1, 4), abs(a1 - 2 * math.pi * (n - 1) / n) < 1e-2, f"~{2 * math.pi * (n - 1) / n:.3f}",
        "keys must be linear; the last frame must not repeat the first")
r.check("loops_seamlessly", round(a2, 4), abs(a2 - 2 * math.pi) < 1e-4, "2*pi", "frame_end + 1 must equal one full turn")
sc.frame_set(start)
r.info.update(frames=n, fps=sc.render.fps, seconds=round(n / sc.render.fps, 2), pivot=piv.name, camera=cam.name)
r.emit()
