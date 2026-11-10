"""Gallery 03: a field of cubes lifted by noise (gauge-geonodes height_grid), coloured by the stored 'height' attribute.

Usage: python ../skills/gauge-core/scripts/run_headless.py scene_terrain.py out=_work/terrain.png [width=1280 height=720 samples=96 percent=100]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa: F401,F403
import kit

P = args_from_argv(out=os.path.join(OUT, "terrain.png"), width=1280, height=720, samples=96, percent=100, res=100)
sc = base_scene(P["width"], P["height"])
gates = []
col = gauge.workspace_make("terrain")
src = kit.rounded_box("terrain_cube", (1, 1, 1), bevel=0.12, segments=2, collection=col)
src.hide_render = True
src.hide_set(True)
# colour by the point attribute stored before instancing: teal -> violet -> amber
spec = {"nodes": {
    "attr": {"type": "ShaderNodeAttribute", "at": [-700, 0], "set": {"attribute_type": "INSTANCER", "attribute_name": "height"}},
    "bands": {"type": "ShaderNodeMath", "at": [-500, 0], "set": {"operation": "MULTIPLY"}, "in": {"Value_001": 6.0}},
    "wrap": {"type": "ShaderNodeMath", "at": [-320, 0], "set": {"operation": "FRACT"}},
    "tone": {"type": "ShaderNodeMix", "at": [-140, 0], "set": {"data_type": "FLOAT"}, "in": {"Factor": 0.18}},
    "ramp": {"type": "ShaderNodeValToRGB", "at": [60, 0], "set": {"color_ramp": {"interpolation": "LINEAR", "stops": [
        [0.0, list(gauge.hex_to_linear("#12bfae")) + [1]], [0.5, list(gauge.hex_to_linear("#5a3fd0")) + [1]],
        [1.0, list(gauge.hex_to_linear("#ffb347")) + [1]]]}}},
    "bsdf": {"type": "ShaderNodeBsdfPrincipled", "at": [380, 0], "in": {"Metallic": 0.1, "Roughness": 0.4}},
    "out": {"type": "ShaderNodeOutputMaterial", "at": [680, 0]}},
    "links": [["attr.Fac", "bands.Value"], ["bands.Value", "wrap.Value"], ["attr.Fac", "tone.A"], ["wrap.Value", "tone.B"],
              ["tone.Result", "ramp.Fac"], ["ramp.Color", "bsdf.Base Color"], ["bsdf.BSDF", "out.Surface"]]}
mat = bpy.data.materials.new("mat_height_bands")
gauge.node_build(mat.node_tree, spec)
src.data.materials.append(mat)
gates.append(call("gauge-geonodes", "gn_make.py", recipe="height_grid", host="terrain_field", collection="terrain",
                  inputs={"Source": "terrain_cube", "Width": 6.0, "Depth": 3.6, "Res X": P["res"], "Res Y": int(P["res"] * 0.6),
                          "Amplitude": 0.7, "Noise Scale": 1.1, "Detail": 4.0, "Roughness": 0.4, "Cube Scale": 6.0 / P["res"] * 0.92,
                          "Seed": 3.0}))
gates.append(call("gauge-geonodes", "gn_gate.py", object="terrain_field", min_instances=2000, max_neighbour_step=0.2))
gates.append(call("gauge-light-render", "frame_camera.py", subject="terrain_field", lens=55, azimuth=14, elevation=34, fill=0.88))
gates.append(call("gauge-light-render", "rig.py", subject="terrain_field", preset="softbox_product", strength=0.5, world_color="#1d222c"))
gates.append(call("gauge-light-render", "render_preset.py", preset="final", resolution=[P["width"], P["height"]]))
gates.append(call("gauge-light-render", "render_check.py", subject="terrain_field", out=P["out"], samples=P["samples"], percent=P["percent"],
                  min_contrast=0.2, min_fit=0.5))
write_gate("terrain", gates)
