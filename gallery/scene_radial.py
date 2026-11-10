"""Gallery 04: two radial arrays (gauge-geonodes radial_array) of bevelled blades in brass and steel, dramatic lighting.

Usage: python ../skills/gauge-core/scripts/run_headless.py scene_radial.py out=_work/radial.png [width=1280 height=720 samples=96 percent=100]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa: F401,F403
import kit
import presets

P = args_from_argv(out=os.path.join(OUT, "radial.png"), width=1280, height=720, samples=96, percent=100)
sc = base_scene(P["width"], P["height"])
gates = []
col = gauge.workspace_make("radial")
blade = kit.rounded_box("radial_blade", (0.55, 0.05, 0.12), bevel=0.012, collection=col)
chunk = kit.rounded_box("radial_chunk", (0.22, 0.16, 0.2), bevel=0.02, collection=col)
for o in (blade, chunk):
    o.hide_render = True
    o.hide_set(True)
kit.assign(blade, presets.make("mat_brass", "metal", "#d9a441", Roughness=0.24))
kit.assign(chunk, presets.make("mat_steel", "brushed_metal", "#b8c0cc", Roughness=0.3))
gates.append(call("gauge-geonodes", "gn_make.py", recipe="radial_array", host="ring_outer", group="radial_outer", collection="radial",
                  inputs={"Instance": "radial_blade", "Count": 48, "Radius": 2.0, "Scale": 1.0}))
gates.append(call("gauge-geonodes", "gn_make.py", recipe="radial_array", host="ring_inner", group="radial_inner", collection="radial",
                  inputs={"Instance": "radial_chunk", "Count": 18, "Radius": 1.0, "Scale": 1.0}))
core = kit.cylinder("radial_core", 0.42, 0.5, 64, bevel=0.05, loc=(0, 0, 0.0), collection=col)
kit.assign(core, presets.make("mat_core", "emissive", "#ff8a3d", strength=4.0))
gates.append(call("gauge-geonodes", "gn_gate.py", object="ring_outer", min_instances=48, max_instances=48))
gates.append(call("gauge-geonodes", "gn_gate.py", object="ring_inner", min_instances=18, max_instances=18))
gates.append(call("gauge-light-render", "frame_camera.py", subject=["ring_outer", "ring_inner", "radial_core"], lens=50, azimuth=18, elevation=52, fill=0.9))
gates.append(call("gauge-light-render", "rig.py", subject=["ring_outer", "ring_inner", "radial_core"], preset="dramatic", ground=True, strength=0.4, ground_color="#14151a",
                  world_color="#0c0e13"))
gates.append(call("gauge-light-render", "render_preset.py", preset="final", resolution=[P["width"], P["height"]]))
gates.append(call("gauge-light-render", "render_check.py", subject=["ring_outer", "ring_inner", "radial_core"], out=P["out"],
                  samples=P["samples"], percent=P["percent"], min_contrast=0.2, min_fit=0.4, max_clip_white=0.05))
write_gate("radial", gates)
