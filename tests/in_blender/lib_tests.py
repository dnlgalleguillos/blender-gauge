import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import gauge
from suite import run, test

TMP = tempfile.mkdtemp(prefix="gauge_lib_")


def fresh():
    gauge.clear_scene()
    bpy.context.scene.camera = None


def add_mesh(name, verts, faces, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    return ob


def cube(name="Box", size=2.0, loc=(0, 0, 0)):
    h = size / 2
    v = [(x, y, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = add_mesh(name, v, f, loc)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


@test
def report_and_params():
    r = gauge.Report("t")
    r.le("a", 1, 2)
    r.ge("b", 1, 2, hint="raise b")
    r.check("w", 5, False, severity="warn")
    d = r.data()
    assert d["pass"] is False and d["failed"] == ["b"], d
    assert d["checks"][1]["hint"] == "raise b" and d["checks"][2]["severity"] == "warn"
    p = gauge.params({"SCRIPT_ARGS": {"x": 2}}, x=1, y="k")
    assert p["x"] == 2 and p["y"] == "k"
    old = sys.argv
    sys.argv = ["blender", "--", "x=5", "name=hello", "flag=true"]
    try:
        p = gauge.params({"SCRIPT_ARGS": {"x": 2}}, x=1, name="", flag=False)
    finally:
        sys.argv = old
    assert p["x"] == 5 and p["name"] == "hello" and p["flag"] is True, p


@test
def clean_cube_has_no_defects():
    fresh()
    ob = cube()
    m = gauge.mesh_stats(ob)
    assert m["faces"] == 6 and m["quads"] == 6 and m["ngons"] == 0, m
    assert m["closed"] and abs(m["volume"] - 8.0) < 1e-4 and not m["inverted"], m
    assert m["loose_verts"] == m["zero_area_faces"] == m["duplicate_verts"] == m["non_manifold_edges"] == 0, m
    r = gauge.Report("m")
    gauge.mesh_gate(r, [ob], max_ngons=0, require_closed=True)
    assert r.ok, r.failed()


@test
def defects_are_detected():
    fresh()
    ob = cube("Flip")
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    assert gauge.mesh_stats(ob)["inverted"] is True
    plane = add_mesh("Open", [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(0, 1, 2, 3)], (5, 0, 0))
    m = gauge.mesh_stats(plane)
    assert m["boundary_edges"] == 4 and m["closed"] is False, m
    ng = add_mesh("Ngon", [(0, 0, 0), (1, 0, 0), (1.5, 1, 0), (0.5, 1.6, 0), (-0.5, 1, 0)], [(0, 1, 2, 3, 4)], (9, 0, 0))
    assert gauge.mesh_stats(ng)["ngons"] == 1
    dup = add_mesh("Dup", [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0)], [(0, 1, 2)], (12, 0, 0))
    assert gauge.mesh_stats(dup)["duplicate_verts"] == 1
    loose = add_mesh("Loose", [(0, 0, 0), (1, 0, 0), (0, 1, 0), (5, 5, 5)], [(0, 1, 2)], (15, 0, 0))
    assert gauge.mesh_stats(loose)["loose_verts"] == 1
    r = gauge.Report("m")
    gauge.mesh_gate(r, [ob, plane, ng, dup, loose], max_ngons=0)
    names = {c["name"] for c in r.failed()}
    assert {"inverted_volume", "ngons", "duplicate_verts", "loose_verts"} <= names, names


@test
def evaluated_modifiers_are_measured():
    fresh()
    ob = cube()
    mod = ob.modifiers.new("Sub", "SUBSURF")
    mod.levels = 2
    assert gauge.mesh_stats(ob)["faces"] == 96


@test
def uv_density_and_bounds():
    fresh()
    ob = cube()
    ob.data.uv_layers.new(name="UVMap")
    uv = ob.data.uv_layers.active.data
    for poly in ob.data.polygons:
        for i, li in enumerate(poly.loop_indices):
            uv[li].uv = [(0, 0), (1, 0), (1, 1), (0, 1)][i]
    m = gauge.mesh_stats(ob)
    assert m["uv_layers"] == 1 and m["uv_out_of_bounds_faces"] == 0, m
    assert m["texel_density_cv"] < 0.01, m
    for li in ob.data.polygons[0].loop_indices:
        uv[li].uv = uv[li].uv * 3.0
    m = gauge.mesh_stats(ob)
    assert m["uv_out_of_bounds_faces"] == 1 and m["texel_density_cv"] > 0.1, m


@test
def bounds_and_pick():
    fresh()
    a = cube("A", 2, (0, 0, 0))
    b = cube("B", 2, (10, 0, 0))
    col = bpy.data.collections.new("Group")
    bpy.context.scene.collection.children.link(col)
    col.objects.link(b)
    bpy.context.scene.collection.objects.unlink(b)
    assert [o.name for o in gauge.pick("Group")] == ["B"]
    assert [o.name for o in gauge.pick("A")] == ["A"]
    assert len(gauge.pick(None)) == 2
    lo, hi = gauge.bounds([a, b])
    assert abs(lo.x + 1) < 1e-5 and abs(hi.x - 11) < 1e-5
    assert gauge.size_of([a]) == (2.0, 2.0, 2.0)


@test
def framing_detects_cropping():
    fresh()
    ob = cube("Subject", 2)
    cam_data = bpy.data.cameras.new("C")
    cam = bpy.data.objects.new("C", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.location = (0, -8, 0)
    cam.rotation_euler = (1.5708, 0, 0)
    bpy.context.view_layer.update()
    f = gauge.framing(bpy.context.scene, cam, [ob])
    assert f["corners_inside"] == 8 and f["margin"] > 0 and 0.01 < f["fill"] < 0.5, f
    ob.location.x = 6
    bpy.context.view_layer.update()
    f2 = gauge.framing(bpy.context.scene, cam, [ob])
    assert f2["margin"] < 0, f2
    r = gauge.Report("f")
    gauge.framing_gate(r, bpy.context.scene, [ob])
    assert not r.ok


@test
def image_numbers():
    h, w = 64, 96
    a = np.zeros((h, w, 4), np.float32)
    a[..., 3] = 1
    a[:, : w // 2, :3] = [0.9, 0.1, 0.1]
    a[:, w // 2:, :3] = [0.1, 0.1, 0.9]
    st = gauge.image_stats(a)
    assert st["clip_white"] == 0 and st["clip_black"] == 0 and 0.1 < st["mean_luma"] < 0.4, st
    pal = st["palette"]
    assert len(pal) == 2 and {c["hex"] for c in pal} == {"#e51a1a", "#1a1ae5"}, pal
    bright = a.copy()
    bright[..., :3] = np.clip(bright[..., :3] + 0.1, 0, 1)
    cmp = gauge.compare(bright, a)
    assert 0.09 < cmp["mean_abs_error"] < 0.11 and cmp["luma_shift"] > 0.05 and cmp["luma_correlation"] > 0.99, cmp
    grid = gauge.sharpness_grid(a)
    assert len(grid) == 4 and max(max(r) for r in grid) == 1.0
    assert gauge.linear_to_hex(gauge.hex_to_linear("#336699")) == "#336699"


@test
def png_roundtrip_and_exposure_gate():
    img = bpy.data.images.new("t", 32, 32)
    px = np.zeros((32, 32, 4), np.float32)
    px[..., 3] = 1
    px[:, :16, :3] = 0.8
    px[:, 16:, :3] = 0.05
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = os.path.join(TMP, "t.png")
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    back = gauge.load_pixels(os.path.join(TMP, "t.png"))
    assert back.shape == (32, 32, 4) and abs(back[0, 0, 0] - 0.8) < 0.01 and abs(back[0, 31, 0] - 0.05) < 0.01
    r = gauge.Report("e")
    gauge.exposure_gate(r, os.path.join(TMP, "t.png"))
    assert r.ok, r.failed()
    # a white square image must fail
    px[..., :3] = 1.0
    img = bpy.data.images.new("w", 32, 32)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = os.path.join(TMP, "w.png")
    img.file_format = "PNG"
    img.save()
    r2 = gauge.Report("e2")
    gauge.exposure_gate(r2, os.path.join(TMP, "w.png"))
    assert not r2.ok and "clipped_white" in {c["name"] for c in r2.failed()}


@test
def shader_dump_build_roundtrip():
    fresh()
    mat = bpy.data.materials.new("Rough")
    nt = mat.node_tree
    nt.nodes.clear()
    spec = {"nodes": {
        "tex": {"type": "ShaderNodeTexNoise", "set": {"noise_dimensions": "3D"}, "in": {"Scale": 7.5}},
        "ramp": {"type": "ShaderNodeValToRGB", "set": {"color_ramp": {"interpolation": "LINEAR",
                 "stops": [[0.2, [0, 0, 0, 1]], [0.8, [1, 0.5, 0, 1]]]}}},
        "bsdf": {"type": "ShaderNodeBsdfPrincipled", "in": {"Metallic": 0.9, "Roughness": 0.35, "Base Color": "#ff8800"}},
        "out": {"type": "ShaderNodeOutputMaterial"}},
        "links": [["tex.Fac", "ramp.Fac"], ["ramp.Color", "bsdf.Base Color"], ["bsdf.BSDF", "out.Surface"]]}
    gauge.node_build(nt, spec)
    assert abs(nt.nodes["bsdf"].inputs["Metallic"].default_value - 0.9) < 1e-6
    assert nt.nodes["tex"].inputs["Scale"].default_value == 7.5
    d = gauge.node_dump(nt)
    assert d["nodes"]["tex"]["in"]["Scale"] == 7.5
    assert d["nodes"]["bsdf"]["in"]["Roughness"] == 0.35
    assert ["bsdf.BSDF", "out.Surface"] in d["links"], d["links"]
    mat2 = bpy.data.materials.new("Copy")
    gauge.node_build(mat2.node_tree, d)
    d2 = gauge.node_dump(mat2.node_tree)
    strip = lambda x: {k: {a: b for a, b in v.items() if a != "at"} for k, v in x["nodes"].items()}
    assert strip(d) == strip(d2), (strip(d), strip(d2))
    assert sorted(d["links"]) == sorted(d2["links"])
    txt = gauge.node_text(nt)
    assert "bsdf [BsdfPrincipled]" in txt and "<- ramp.Color" in txt, txt


@test
def geometry_nodes_build_and_gate():
    fresh()
    g = bpy.data.node_groups.new("Grid", "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    spec = {"nodes": {
        "grid": {"type": "GeometryNodeMeshGrid", "in": {"Size X": 4.0, "Size Y": 4.0, "Vertices X": 5, "Vertices Y": 5}},
        "out": {"type": "NodeGroupOutput"}},
        "links": [["grid.Mesh", "out.Geometry"]]}
    gauge.node_build(g, spec)
    ob = add_mesh("Host", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    md = ob.modifiers.new("GN", "NODES")
    md.node_group = g
    assert gauge.mesh_stats(ob)["faces"] == 16
    r = gauge.Report("n")
    gauge.node_gate(r, g)
    assert r.ok, r.failed()
    g.links.clear()
    r2 = gauge.Report("n2")
    gauge.node_gate(r2, g)
    assert "Grid: group_output_connected" in {c["name"] for c in r2.failed()}


@test
def node_gate_flags_color_data_mistakes():
    fresh()
    mat = bpy.data.materials.new("M")
    nt = mat.node_tree
    img = bpy.data.images.new("rough_tex", 4, 4)
    img.colorspace_settings.name = "sRGB"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    bsdf = nt.nodes["Principled BSDF"]
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Roughness"])
    empty = nt.nodes.new("ShaderNodeTexImage")
    r = gauge.Report("mat")
    gauge.node_gate(r, nt, "M")
    bad = {c["name"] for c in r.failed()}
    assert "M: data_textures_non_color" in bad and "M: image_nodes_have_image" in bad, bad
    img.colorspace_settings.name = "Non-Color"
    r = gauge.Report("mat")
    gauge.node_gate(r, nt, "M")
    assert "M: data_textures_non_color" not in {c["name"] for c in r.failed()}


@test
def scene_gate_flags_hygiene():
    fresh()
    ob = cube("Cube")
    ob.scale = (2, 2, 2)
    r = gauge.Report("s")
    gauge.scene_gate(r)
    by = {c["name"]: c for c in r.checks}
    assert by["default_object_names"]["ok"] is False and by["unapplied_scale"]["ok"] is False
    assert by["unit_system"]["ok"] and by["unit_scale"]["ok"]
    assert r.ok is True or all(c.get("severity") == "warn" for c in r.failed())
    ob.scale = (-1, 1, 1)
    r = gauge.Report("s")
    gauge.scene_gate(r)
    assert "negative_scale" in {c["name"] for c in r.failed()}


@test
def workspace_is_dry_run_first():
    fresh()
    col = gauge.workspace_make("Work")
    ob = cube("Part")
    bpy.context.scene.collection.objects.unlink(ob)
    col.objects.link(ob)
    dry = gauge.workspace_remove("Work")
    assert dry["found"] and dry["objects"] == ["Part"] and dry["deleted"] is False
    assert "Part" in bpy.data.objects and "Work" in bpy.data.collections
    done = gauge.workspace_remove("Work", confirm=True)
    assert done["deleted"] and "Part" not in bpy.data.objects and "Work" not in bpy.data.collections
    assert gauge.workspace_remove("Nope") == {"collection": "Nope", "found": False}


@test
def render_restores_settings():
    fresh()
    ob = cube("Subject")
    cam = bpy.data.objects.new("C", bpy.data.cameras.new("C"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (0, -7, 0)
    cam.rotation_euler = (1.5708, 0, 0)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = 128, 96
    before = (sc.render.engine, sc.render.resolution_percentage, sc.cycles.samples)
    out = gauge.render(os.path.join(TMP, "r.png"), samples=2, percent=50)
    assert os.path.getsize(out) > 200
    assert (sc.render.engine, sc.render.resolution_percentage, sc.cycles.samples) == before
    a = gauge.load_pixels(out)
    assert a.shape[:2] == (48, 64), a.shape


@test
def geometry_nodes_inputs_by_name():
    fresh()
    g = bpy.data.node_groups.new("Inputs", "GeometryNodeTree")
    for nm, st in (("Geometry", "NodeSocketGeometry"), ("Size", "NodeSocketFloat"), ("Count", "NodeSocketInt"),
                   ("Offset", "NodeSocketVector"), ("Enabled", "NodeSocketBool"), ("Mat", "NodeSocketMaterial"),
                   ("Target", "NodeSocketObject")):
        g.interface.new_socket(nm, in_out="INPUT", socket_type=st)
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    mat = bpy.data.materials.new("Paint")
    tgt = cube("Tgt")
    ob = cube("Host")
    md = ob.modifiers.new("GN", "NODES")
    md.node_group = g
    gauge.gn_set(md, Size=2.5, Count=7, Offset=(1, 2, 3), Enabled=True, Mat="Paint", Target="Tgt")
    assert gauge.gn_get(md, "Size") == 2.5 and gauge.gn_get(md, "Count") == 7
    assert gauge.gn_get(md, "Offset") == [1.0, 2.0, 3.0] and gauge.gn_get(md, "Enabled") in (True, 1)
    assert gauge.gn_get(md, "Mat") == mat and gauge.gn_get(md, "Target") == tgt
    gauge.gn_set(md, Size=900, Count=3.0)  # plain int into a Float input, float into an Int input: must still land
    assert gauge.gn_get(md, "Size") == 900.0 and gauge.gn_get(md, "Count") == 3
    try:
        gauge.gn_set(md, Nope=1)
        raise AssertionError("expected KeyError")
    except KeyError as e:
        assert "Nope" in str(e) and "Size" in str(e)


@test
def instance_counting():
    fresh()
    src = cube("Src", 0.1)
    g = bpy.data.node_groups.new("Inst", "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gauge.node_build(g, {"nodes": {
        "grid": {"type": "GeometryNodeMeshGrid", "in": {"Vertices X": 6, "Vertices Y": 6}},
        "inst": {"type": "GeometryNodeInstanceOnPoints"},
        "cube": {"type": "GeometryNodeMeshCube"},
        "out": {"type": "NodeGroupOutput"}},
        "links": [["grid.Mesh", "inst.Points"], ["cube.Mesh", "inst.Instance"], ["inst.Instances", "out.Geometry"]]})
    host = add_mesh("Host", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    host.modifiers.new("GN", "NODES").node_group = g
    assert gauge.instance_count(host) == 36, gauge.instance_count(host)


@test
def visible_area_light_in_shot_is_caught():
    fresh()
    cube("Subject", 1.0)
    cam = bpy.data.objects.new("C", bpy.data.cameras.new("C"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location, cam.rotation_euler = (0, -8, 0), (1.5708, 0, 0)
    bpy.context.scene.camera = cam
    lt = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA"))
    lt.data.size = 4.0
    lt.visible_camera = True  # Blender 5.3 creates lights camera-invisible; the check must work when they are not
    lt.location = (0, -4, 0)
    lt.rotation_euler = (-1.5708, 0, 0)
    bpy.context.scene.collection.objects.link(lt)
    bpy.context.view_layer.update()
    assert gauge.lights_in_frame(bpy.context.scene, cam) == ["L"]
    lt.visible_camera = False
    assert gauge.lights_in_frame(bpy.context.scene, cam) == []
    lt.visible_camera = True
    lt.location = (12, -4, 0)
    bpy.context.view_layer.update()
    assert gauge.lights_in_frame(bpy.context.scene, cam) == []


@test
def occlusion_is_measured():
    fresh()
    subject = cube("S", 1.0)
    blocker = cube("Blocker", 2.0, (0, -3, 0))
    side = cube("Side", 2.0, (6, -3, 0))
    bpy.context.view_layer.update()
    origin = Vector((0, -9, 0))
    assert gauge.occluded_by(origin, subject, [subject, blocker, side]) == ["Blocker"]
    assert gauge.occluded_by(origin, subject, [subject, side]) == []


run()
