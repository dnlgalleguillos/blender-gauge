"""WavyCubes: a procedural wavy-cubes wallpaper (Geometry Nodes + shader) built with the Blender Gauge skills.

Usage: python skills/gauge-core/scripts/run_headless.py examples/wavy-cubes/build_wavy.py [key=value ...]
Keys: out (png, default _out/wavy_final.png), blend (save path), width / height (1920x1080), samples (100), percent (100),
render (bool, true), scan (bool: build and measure only, no camera or render), reference (optional image: also report the
distance to it), plus every tuning parameter in the params() call below (noise, grid, shader, camera, light).
Every deviation from a "plain" setup is a parameter, so each change is a visible, measured decision. The render takes
about 7 minutes at 1920x1080 on a 4-core CPU; use width=960 height=540 samples=24 for a 40-second preview.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAUGE = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(GAUGE, "lib"))
for sk in ("gauge-modeling", "gauge-materials", "gauge-geonodes", "gauge-light-render"):
    sys.path.append(os.path.join(GAUGE, "skills", sk, "scripts"))

import bpy
from mathutils import Vector

import gauge
import kit

P = gauge.params(globals(), out=os.path.join(HERE, "_out", "wavy_final.png"), blend=os.path.join(HERE, "_out", "WavyCubes.blend"),
                 reference=None,
                 width=1920, height=1080, samples=100, percent=100, scan=False, render=True,
                 # grid (the prompt's 2 x 1 m / 50 x 25 has the same 0.04 m spacing; bigger so the grazing view never shows an edge)
                 size_x=4.7, size_y=4.7, res=114, cube_scale=0.0208, underlay=True,
                 # noise, as in the prompt unless noted
                 w=0.9, scale=0.8, detail=3.0, roughness=0.5, lacunarity=2.7, distortion=0.0,
                 from_min=0.2, from_max=1.8, to_min=-0.3, to_max=1.0,
                 # shader
                 bands=7.0, metallic=0.0, mat_roughness=0.35, beige="#CBBCA8", teal="#5E7F7A",
                 # camera and light
                 lens=50.0, elevation=24.0, distance=2.0, fstop=1.4, plane_rot=35.0, ahead=0.5,
                 world_color="#C2C4C6", world_strength=1.8, sun_strength=1.0, sun_angle=14.0, sun_az=-55.0, sun_el=42.0)

sc = bpy.context.scene
gauge.clear_scene()
sc.render.resolution_x, sc.render.resolution_y = P["width"], P["height"]
col = gauge.workspace_make("WavyCubes")

# 1. the instanced cube: 2 m, Bevel 0.08 / 3 segments applied, hidden from viewport and render
cube = kit.rounded_box("Cube", (2, 2, 2), bevel=0.08, segments=3, collection=col)
cube.hide_render = True
cube.hide_set(True)

# 2. Geometry Nodes tree = the height_grid recipe with the prompt's values and the prompt's extra nodes
with open(os.path.join(GAUGE, "skills", "gauge-geonodes", "recipes", "height_grid.json")) as fh:
    spec = json.load(fh)
spec.pop("description", None)
spec["interface"]["inputs"].append({"name": "Material", "type": "Material"})
spec["nodes"]["noise"]["in"] = {"Lacunarity": P["lacunarity"], "Distortion": P["distortion"]}
spec["nodes"]["lift"]["in"] = {"From Min": P["from_min"], "From Max": P["from_max"], "To Min": P["to_min"]}
spec["nodes"]["store"]["in"] = {"Name": "noise"}
spec["links"] = [l for l in spec["links"] if l != ["noise.Fac", "norm.Value"] and l != ["norm.Result", "store.Value"]
                 and l != ["inst.Instances", "out.Geometry"]]
spec["links"] += [["noise.Fac", "store.Value"], ["inst.Instances", "setmat.Geometry"], ["gin.Material", "setmat.Material"],
                  ["setmat.Geometry", "smooth.Geometry"], ["smooth.Geometry", "out.Geometry"]]
spec["nodes"].pop("norm", None)
spec["nodes"]["setmat"] = {"type": "GeometryNodeSetMaterial", "at": [640, 100]}
spec["nodes"]["smooth"] = {"type": "GeometryNodeSetShadeSmooth", "at": [880, 100], "set": {"domain": "FACE"}, "in": {"Shade Smooth": True}}
spec["nodes"]["out"]["at"] = [1120, 100]

# 3. the material: the prompt's tree, with the colour source switched to the stored 'noise' attribute (the prompt's own fallback)
mat = bpy.data.materials.new("Material")
mat_spec = {"nodes": {
    "attr": {"type": "ShaderNodeAttribute", "at": [-900, -300], "set": {"attribute_type": "INSTANCER", "attribute_name": "noise"}},
    "k": {"type": "ShaderNodeMath", "at": [-700, -300], "set": {"operation": "MULTIPLY"}, "in": {"Value_001": P["bands"]}},
    "band": {"type": "ShaderNodeMath", "at": [-520, -300], "set": {"operation": "FRACT"}},
    "one": {"type": "ShaderNodeValue", "at": [-520, 100]},
    "minus": {"type": "ShaderNodeValue", "at": [-520, -60]},
    "sub": {"type": "ShaderNodeMath", "at": [-300, 40], "set": {"operation": "SUBTRACT"}},
    "mul": {"type": "ShaderNodeMath", "at": [-120, 40], "set": {"operation": "MULTIPLY"}},
    "add": {"type": "ShaderNodeMath", "at": [60, 40], "set": {"operation": "ADD"}},
    "ramp": {"type": "ShaderNodeValToRGB", "at": [260, 40], "set": {"color_ramp": {"interpolation": "EASE", "stops": [
        [0.13, list(gauge.hex_to_linear(P["beige"])) + [1]], [0.618, list(gauge.hex_to_linear(P["teal"])) + [1]]]}}},
    "curves": {"type": "ShaderNodeRGBCurve", "at": [560, 40]},
    "bsdf": {"type": "ShaderNodeBsdfPrincipled", "at": [860, 40], "in": {"Metallic": P["metallic"], "Roughness": P["mat_roughness"],
                                                                        "IOR": 1.45, "Alpha": 1.0}},
    "out": {"type": "ShaderNodeOutputMaterial", "at": [1160, 40]}},
    "links": [["attr.Fac", "k.Value"], ["k.Value", "band.Value"], ["one.Value", "sub.Value"], ["band.Value", "sub.Value_001"],
              ["sub.Value", "mul.Value"], ["minus.Value", "mul.Value_001"], ["mul.Value", "add.Value"], ["band.Value", "add.Value_001"],
              ["add.Value", "ramp.Fac"], ["ramp.Color", "curves.Color"], ["curves.Color", "bsdf.Base Color"], ["bsdf.BSDF", "out.Surface"]]}
made = gauge.node_build(mat.node_tree, mat_spec)
made["one"].outputs[0].default_value = 1.0
made["minus"].outputs[0].default_value = -0.1
crv = made["curves"].mapping.curves[3]  # combined (C) curve: the prompt's point at (0.386, 0.25)
crv.points.new(0.386, 0.25)
made["curves"].mapping.update()

group = gauge.gn_make("WavyCubes_GN", spec)
plane_me = bpy.data.meshes.new("Plane")
plane_me.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
plane = bpy.data.objects.new("Plane", plane_me)
col.objects.link(plane)
mod = plane.modifiers.new("GeometryNodes", "NODES")
mod.node_group = group
gauge.gn_set(mod, Source="Cube", Material="Material", Width=P["size_x"], Depth=P["size_y"],
             **{"Res X": P["res"], "Res Y": P["res"], "Amplitude": P["to_max"], "Noise Scale": P["scale"], "Detail": P["detail"],
                "Roughness": P["roughness"], "Seed": P["w"], "Cube Scale": P["cube_scale"]})
plane.rotation_euler.z = math.radians(P["plane_rot"])
bpy.context.view_layer.update()

report = gauge.Report("wavy-cubes")
report.info["params"] = {k: v for k, v in P.items() if k not in ("out", "blend")}
gauge.node_gate(report, group, "WavyCubes_GN")
gauge.node_gate(report, mat.node_tree, "Material")
n = gauge.instance_count(plane)
report.check("instances", n, n >= P["res"] * P["res"] * 0.99, f">= {P['res'] ** 2}", "Geometry Nodes produced fewer instances than grid points")
# neighbour steps need an axis-aligned grid: measure with the plane unrotated
rot = plane.rotation_euler.z
plane.rotation_euler.z = 0.0
bpy.context.view_layer.update()
gs = gauge.grid_step(gauge.instance_positions(plane))
plane.rotation_euler.z = rot
bpy.context.view_layer.update()
report.info["grid"] = gs
report.info["instances"] = n
if P["scan"]:
    report.emit()
else:
    # 4. camera: grazing, diagonal over the grid, focus on a hill near the centre
    pos = gauge.instance_positions(plane)
    near = [p for p in pos if abs(p[0]) < 0.5 and abs(p[1] - P["ahead"]) < 0.5]
    hill = max(near or pos, key=lambda p: p[2])
    focus_pt = Vector((0.0, 0.0, hill[2]))
    plane.location = Vector((0.0, P["ahead"], 0.0))
    if P["underlay"]:  # dark base under the cubes: the world would otherwise show through the slits between deep columns
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=P["size_x"] / 2 + 0.1)
        me_u = bpy.data.meshes.new("Underlay")
        bm.to_mesh(me_u)
        bm.free()
        under = bpy.data.objects.new("Underlay", me_u)
        under.location = (0.0, P["ahead"], min(p[2] for p in pos) - 0.03)
        under.rotation_euler.z = math.radians(P["plane_rot"])
        mu = bpy.data.materials.new("Underlay")
        mu.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*gauge.hex_to_linear("#2b3835"), 1.0)
        mu.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
        me_u.materials.append(mu)
        col.objects.link(under)
    e = math.radians(P["elevation"])
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    col.objects.link(cam)
    cam.data.lens = P["lens"]
    cam.location = focus_pt + Vector((0.0, -math.cos(e), math.sin(e))) * P["distance"]
    cam.rotation_euler = (focus_pt - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = P["fstop"]
    cam.data.dof.focus_distance = (cam.location - focus_pt).length
    cam.data.clip_start, cam.data.clip_end = 0.01, 100.0
    sc.camera = cam
    bpy.context.view_layer.update()

    # no edge of the grid may be visible: cast the four frame corners and the middle of each frame edge onto the surface
    half = P["size_x"] / 2 - 0.12
    plane_inv = plane.matrix_world.inverted()
    z0 = sum(p[2] for p in pos) / len(pos)
    worst = 9.0
    for v in list(cam.data.view_frame(scene=sc)) + [(a + b) / 2 for a, b in zip(list(cam.data.view_frame(scene=sc)), list(cam.data.view_frame(scene=sc))[1:] + list(cam.data.view_frame(scene=sc))[:1])]:
        d = (cam.matrix_world.to_3x3() @ Vector(v)).normalized()
        if d.z >= -1e-4:
            worst = -9.0
            continue
        t = (z0 - cam.location.z) / d.z
        local = plane_inv @ (cam.location + d * t)
        worst = min(worst, half - max(abs(local.x), abs(local.y)))
    report.check("grid_edge_not_visible", round(worst, 3), worst > 0, "> 0 m inside the grid",
                 "the frame sees past the grid: raise Width/Depth, lower the camera elevation or move the plane under the shot")
    from bpy_extras.object_utils import world_to_camera_view
    near_pts = sorted(pos, key=lambda p: (Vector(p) - focus_pt).length)[:2]
    ndc = [world_to_camera_view(sc, cam, Vector(p)) for p in near_pts]
    spacing = (Vector(near_pts[0]) - Vector(near_pts[1])).length
    across = 1.0 / max(1e-6, math.hypot(ndc[0].x - ndc[1].x, (ndc[0].y - ndc[1].y) * P["height"] / P["width"])) * spacing / (P["size_x"] / (P["res"] - 1))
    report.check("cubes_across_frame_at_focus", round(across, 1), 30 <= across <= 48, "30..48 (readable stairs, not noise)",
                 "cubes too small or too big in frame: move the camera closer or farther")
    report.info["camera"] = {"location": [round(v, 3) for v in cam.location], "focus": [round(v, 3) for v in focus_pt],
                             "focus_distance": round(cam.data.dof.focus_distance, 3)}

    # 5. world and light: warm light-grey world + a soft sun from the side
    world = bpy.data.worlds.new("World")
    sc.world = world
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*gauge.hex_to_linear(P["world_color"]), 1.0)
    bg.inputs["Strength"].default_value = P["world_strength"]
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy, sun.data.angle = P["sun_strength"], math.radians(P["sun_angle"])
    sun.rotation_euler = (math.radians(90 - P["sun_el"]), 0, math.radians(P["sun_az"]))
    col.objects.link(sun)

    # 6. render settings: Cycles CPU, noise threshold 0.01, 100 samples, denoise, AgX
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.01
    sc.cycles.samples = int(P["samples"])
    sc.cycles.use_denoising = True
    sc.cycles.preview_samples = 100
    sc.cycles.use_preview_adaptive_sampling = True
    sc.cycles.preview_adaptive_threshold = 0.1
    sc.view_settings.view_transform = "AgX"
    look_used = None
    for look in ("AgX - Base Contrast", "AgX - Medium Contrast", "Medium Contrast"):
        try:
            sc.view_settings.look = look
            look_used = look
            break
        except TypeError:
            continue
    report.info["look"] = look_used
    sc.render.resolution_percentage = int(P["percent"])
    os.makedirs(os.path.dirname(os.path.abspath(P["blend"])), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=P["blend"])
    if P["render"]:
        path = gauge.render(P["out"], samples=int(P["samples"]), percent=int(P["percent"]))
        st_img = gauge.exposure_gate(report, path, max_clip_white=0.03, min_contrast=0.2)
        if P["reference"]:
            ref = gauge.load_pixels(P["reference"])
            report.info["vs_reference"] = gauge.compare(gauge.load_pixels(path), ref)
            report.info["reference_stats"] = gauge.image_stats(ref)
        report.info["out"] = path
    report.emit()
