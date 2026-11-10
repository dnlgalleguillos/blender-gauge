"""Apply a render preset (engine, samples, denoise, colour management) and gate the settings.

Usage (live):  run_blender_script path=skills/gauge-light-render/scripts/render_preset.py args={"preset": "preview"}
Args: preset (draft, preview, final), engine (CYCLES default, or BLENDER_EEVEE), resolution ([w, h]), look
      ("AgX - Punchy" etc., optional), transparent (bool, false), apply (bool, true; false = only gate).
draft  = 16 samples, 50 % size    preview = 64 samples, 75 %    final = 256 samples, 100 %  (Cycles, denoise on).
Prints one GAUGE_JSON line, gate "render-settings".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge

P = gauge.params(globals(), preset="preview", engine="CYCLES", resolution=None, look=None, transparent=False, apply=True)
SAMPLES = {"draft": (16, 50), "preview": (64, 75), "final": (256, 100)}
if P["preset"] not in SAMPLES:
    raise KeyError(f"unknown preset '{P['preset']}' (have: {sorted(SAMPLES)})")
sc = bpy.context.scene
samples, pct = SAMPLES[P["preset"]]
notes = []
if P["apply"]:
    sc.render.engine = P["engine"]
    if P["resolution"]:
        sc.render.resolution_x, sc.render.resolution_y = P["resolution"]
    sc.render.resolution_percentage = pct
    sc.render.film_transparent = bool(P["transparent"])
    if P["engine"] == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.device = "CPU" if sc.cycles.device not in ("CPU", "GPU") else sc.cycles.device
    try:
        sc.view_settings.view_transform = "AgX"
    except TypeError:
        notes.append("AgX view transform not available; left unchanged")
    if P["look"]:
        try:
            sc.view_settings.look = P["look"]
        except TypeError:
            notes.append(f"look '{P['look']}' rejected (try 'AgX - Punchy' or 'AgX - Base Contrast')")
r = gauge.Report("render-settings")
r.check("engine", sc.render.engine, sc.render.engine in ("CYCLES", "BLENDER_EEVEE"), "CYCLES or BLENDER_EEVEE")
if sc.render.engine == "CYCLES":
    r.ge("cycles_samples", sc.cycles.samples, 8)
    r.check("denoising_on", sc.cycles.use_denoising, sc.cycles.use_denoising or sc.cycles.samples >= 512, True,
            "low sample counts need the denoiser")
r.check("view_transform", sc.view_settings.view_transform, sc.view_settings.view_transform not in ("Standard", "Raw"),
        "AgX or Filmic", "Standard clips highlights; use AgX", severity="warn")
r.check("resolution", [sc.render.resolution_x, sc.render.resolution_y], sc.render.resolution_x >= 64 and sc.render.resolution_y >= 64, ">= 64 px")
r.info.update(preset=P["preset"], percent=sc.render.resolution_percentage, notes=notes,
              output_px=[sc.render.resolution_x * sc.render.resolution_percentage // 100, sc.render.resolution_y * sc.render.resolution_percentage // 100])
r.emit()
