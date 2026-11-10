"""Gallery 02: a hard-surface crate built with gauge-modeling, lit and framed with gauge-light-render, gated end to end.

Usage: python ../skills/gauge-core/scripts/run_headless.py scene_crate.py out=_work/crate.png [width=1280 height=720 samples=96 percent=100]
Also saves _work/crate.blend (used by match_demo.py) and _work/crate.json (every gate that ran).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa: F401,F403
import presets
import kit

P = args_from_argv(out=os.path.join(OUT, "crate.png"), width=1280, height=720, samples=96, percent=100)
sc = base_scene(P["width"], P["height"])
gates = []
gates.append(call("gauge-modeling", "build_prop.py", name="crate", max_ngons=200))
wood = presets.make("mat_wood", "wood", "#b07a45")
dark = presets.make("mat_dark_wood", "wood", "#6b4426")
steel = presets.make("mat_steel", "brushed_metal", "#c3c8d0", Roughness=0.32)
brass = presets.make("mat_brass", "metal", "#d4a24a", Roughness=0.28)
for name, mat in (("body", wood), ("lid", dark), ("strap_a", steel), ("strap_b", steel), ("plate", brass)):
    kit.assign(bpy.data.objects[f"crate_{name}"], mat)
for o in bpy.data.collections["crate"].objects:
    if o.name.startswith("crate_bolt"):
        kit.assign(o, brass)
gates.append(call("gauge-materials", "material_gate.py", collection="crate"))
gates.append(call("gauge-light-render", "frame_camera.py", subject="crate", lens=70, azimuth=34, elevation=22, fill=0.7, aperture=5.6))
gates.append(call("gauge-light-render", "rig.py", subject="crate", preset="three_point", ground=True, ground_color="#707075", world_color="#59626f"))
gates.append(call("gauge-light-render", "render_preset.py", preset="final", resolution=[P["width"], P["height"]]))
gates.append(call("gauge-light-render", "render_check.py", subject="crate", out=P["out"], samples=P["samples"], percent=P["percent"],
                  min_contrast=0.2, min_fit=0.4))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "crate.blend"), copy=True)
write_gate("crate", gates)
