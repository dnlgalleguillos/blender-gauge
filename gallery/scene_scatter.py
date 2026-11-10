"""Gallery 05: blades scattered over a ground (gauge-geonodes scatter_surface) under an overcast sky.

Usage: python ../skills/gauge-core/scripts/run_headless.py scene_scatter.py out=_work/scatter.png [width=1280 height=720 samples=96 percent=100]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa: F401,F403
import bmesh
import kit
import presets

P = args_from_argv(out=os.path.join(OUT, "scatter.png"), width=1280, height=720, samples=96, percent=100, density=900)
sc = base_scene(P["width"], P["height"])
gates = []
col = gauge.workspace_make("scatter")
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=5, radius1=0.018, radius2=0.0, depth=0.32,
                      matrix=__import__("mathutils").Matrix.Translation((0, 0, 0.16)))
me = bpy.data.meshes.new("scatter_blade")
bm.to_mesh(me)
bm.free()
blade = bpy.data.objects.new("scatter_blade", me)
col.objects.link(blade)
blade.hide_render = True
blade.hide_set(True)
kit.assign(blade, presets.make("mat_blade", "plastic", "#8fd65a", Roughness=0.5))
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=8, y_segments=8, size=1.5)
me2 = bpy.data.meshes.new("scatter_ground")
bm.to_mesh(me2)
bm.free()
ground = bpy.data.objects.new("scatter_ground", me2)
col.objects.link(ground)
kit.assign(ground, presets.make("mat_soil", "concrete", "#6b5640"))
gates.append(call("gauge-geonodes", "gn_make.py", recipe="scatter_surface", host="scatter_field", collection="scatter",
                  inputs={"Target": "scatter_ground", "Instance": "scatter_blade", "Density": P["density"], "Seed": 11,
                          "Min Scale": 0.55, "Max Scale": 1.5}))
gates.append(call("gauge-geonodes", "gn_gate.py", object="scatter_field", min_instances=2000))
gates.append(call("gauge-light-render", "frame_camera.py", subject=["scatter_field", "scatter_ground"], lens=60, azimuth=20, elevation=24, fill=0.8,
                  aperture=2.8))
gates.append(call("gauge-light-render", "rig.py", subject=["scatter_ground"], preset="overcast", ground=False, strength=1.8, world_color="#c3d4e6"))
gates.append(call("gauge-light-render", "render_preset.py", preset="final", resolution=[P["width"], P["height"]]))
gates.append(call("gauge-light-render", "render_check.py", subject=["scatter_ground"], out=P["out"], samples=P["samples"], percent=P["percent"],
                  min_contrast=0.15, min_fit=0.4))
write_gate("scatter", gates)
