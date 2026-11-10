"""Create or move a camera so the subject fills a chosen share of the frame, then verify the framing.

Usage (live):  run_blender_script path=skills/gauge-light-render/scripts/frame_camera.py
               args={"subject": "Props", "lens": 85, "azimuth": 25, "elevation": 18, "fill": 0.55}
Args: subject (object/collection), lens (mm, 50), azimuth (deg from the front, 0), elevation (deg above the horizon, 15),
      fill (share of the frame the subject covers along its limiting dimension, width or height, 0.5), name (camera object, "gauge_cam"),
      aperture (f-stop for depth of field; omit to leave DoF off), resolution ([w, h]; default keep).
The distance is solved so the projected bounding box covers `fill`, then widened until a 2 % margin is free on every side; the camera looks at the subject centre.
Prints one GAUGE_JSON line, gate "camera-framing": subject in front of the camera, not cropped, fill within limits.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector

import gauge

P = gauge.params(globals(), subject=None, lens=50.0, azimuth=0.0, elevation=15.0, fill=0.5, name="gauge_cam",
                 aperture=None, resolution=None)
sc = bpy.context.scene
objs = gauge.pick(P["subject"])
b = gauge.bounds(objs)
if b is None:
    raise RuntimeError("subject has no geometry to frame")
lo, hi = b
centre = (lo + hi) / 2
cam = bpy.data.objects.get(P["name"])
if cam is None:
    cam = bpy.data.objects.new(P["name"], bpy.data.cameras.new(P["name"]))
    bpy.context.view_layer.active_layer_collection.collection.objects.link(cam)
cam.data.lens = P["lens"]
cam.data.clip_start, cam.data.clip_end = 0.01, 1000.0
if P["resolution"]:
    sc.render.resolution_x, sc.render.resolution_y = P["resolution"]
sc.camera = cam
a, e = math.radians(P["azimuth"]), math.radians(P["elevation"])
direction = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))


def place(dist):
    cam.location = centre + direction * dist
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    return gauge.framing(sc, cam, objs)


radius = max((hi - lo).length / 2, 0.01)
lo_d, hi_d = radius * 0.6, radius * 400
for _ in range(40):  # fill falls as the camera backs away: bisection on distance
    mid = (lo_d + hi_d) / 2
    f = place(mid)
    if f["behind_camera"] or f["fit"] > P["fill"]:
        lo_d = mid
    else:
        hi_d = mid
dist = (lo_d + hi_d) / 2
f = place(dist)
for _ in range(80):  # perspective makes the near side of the box bigger: keep a 2 % margin on every side
    if f["margin"] >= 0.02:
        break
    dist *= 1.02
    f = place(dist)
cam.data.dof.use_dof = P["aperture"] is not None
if P["aperture"] is not None:
    cam.data.dof.aperture_fstop = P["aperture"]
    cam.data.dof.focus_distance = (cam.location - centre).length

r = gauge.Report("camera-framing")
gauge.framing_gate(r, sc, objs, min_fit=max(0.02, P["fill"] * 0.8), max_fit=min(0.98, P["fill"] * 1.25 + 0.02))
r.info.update(camera=cam.name, lens_mm=P["lens"], distance_m=round((cam.location - centre).length, 3),
              location=[round(v, 3) for v in cam.location], target=[round(v, 3) for v in centre])
r.emit()
