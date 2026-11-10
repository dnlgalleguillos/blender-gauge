"""Render a preview of the scene camera and gate it: exposure, contrast, framing, lights in shot.

Usage (headless, preferred):  python run_headless.py render_check.py --blend scene.blend subject=Props out=/tmp/check.png
Usage (live, small):          run_blender_script path=skills/gauge-light-render/scripts/render_check.py args={"percent": 30, "samples": 16}
Args: subject (object/collection the framing is judged on; default all meshes), out (png), samples (24), percent (50),
      min_fit (0.2), max_fit (0.95), max_clip_white (0.02), max_clip_black (0.1), min_contrast (0.25), reference (png, optional:
      also report distance to that image).
Prints one GAUGE_JSON line, gate "render-check", with image statistics (luma, clipping, contrast, palette) in info.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge

P = gauge.params(globals(), subject=None, out="/tmp/gauge_render_check.png", samples=24, percent=50, min_fit=0.2,
                 max_fit=0.95, max_clip_white=0.02, max_clip_black=0.10, min_contrast=0.25, reference=None)
sc = bpy.context.scene
r = gauge.Report("render-check")
objs = gauge.pick(P["subject"])
gauge.framing_gate(r, sc, objs, min_fit=P["min_fit"], max_fit=P["max_fit"])
gauge.lights_gate(r, sc)
path = gauge.render(P["out"], samples=P["samples"], percent=P["percent"], engine="CYCLES")
gauge.exposure_gate(r, path, P["max_clip_white"], P["max_clip_black"], P["min_contrast"])
if P["reference"]:
    r.info["vs_reference"] = gauge.compare(gauge.load_pixels(path), gauge.load_pixels(P["reference"]))
r.info["out"] = path
r.emit()
