import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

KIT = skill_script("gauge-modeling", "kit.py")
sys.path.insert(0, os.path.dirname(KIT))
import kit  # noqa: E402


@test
def kit_builds_measured_parts():
    fresh()
    b = kit.rounded_box("b", (1.0, 0.6, 0.4), bevel=0.02, loc=(0, 0, 0.2))
    assert [round(d, 3) for d in b.dimensions] == [1.0, 0.6, 0.4], tuple(b.dimensions)
    m = gauge.mesh_stats(b)
    assert m["closed"] and m["ngons"] == 0 and m["faces"] > 6 and not m["inverted"], m
    c = kit.cylinder("c", 0.1, 0.3, 24, bevel=0.01)
    assert abs(c.dimensions.z - 0.3) < 1e-4 and abs(c.dimensions.x - 0.2) < 2e-3, tuple(c.dimensions)
    assert gauge.mesh_stats(c)["closed"]
    bolt = kit.bolt_head("bolt", 0.012, 0.008)
    assert abs(bolt.dimensions.z - 0.008) < 1e-6


@test
def rebuild_replaces_not_duplicates():
    fresh()
    kit.rounded_box("same", (1, 1, 1))
    kit.rounded_box("same", (2, 2, 2))
    assert [o.name for o in bpy.data.objects].count("same") == 1 and "same.001" not in bpy.data.objects
    assert bpy.data.objects["same"].dimensions.x == 2.0


@test
def holes_cut_through_the_thin_axis():
    fresh()
    plate = kit.rounded_box("plate", (0.3, 0.012, 0.18), bevel=0.003)
    before = gauge.mesh_stats(plate)["faces"]
    kit.cut_holes(plate, [(-0.1, 0, 0.012), (0.1, 0, 0.012)])
    m = gauge.mesh_stats(plate)
    assert m["faces"] > before + 40 and m["closed"], m
    assert not plate.modifiers and [round(d, 3) for d in plate.dimensions] == [0.3, 0.012, 0.18]
    assert "plate_cutter0" not in bpy.data.objects
    # the holes are real: a ray along Y through the hole centre must miss the plate
    dg = bpy.context.evaluated_depsgraph_get()
    hit = plate.ray_cast(Vector((-0.1, -1, 0)), Vector((0, 1, 0)), depsgraph=dg)[0]
    solid = plate.ray_cast(Vector((0.0, -1, 0)), Vector((0, 1, 0)), depsgraph=dg)[0]
    assert (not hit) and solid


from mathutils import Vector  # noqa: E402


@test
def build_prop_demo_passes_its_gate():
    fresh()
    g, _ = run_script(skill_script("gauge-modeling", "build_prop.py"), name="crate", max_ngons=100)
    gate = g[0]
    assert gate["gate"] == "build-prop" and gate["pass"], gate["failed"]
    assert len(gate["info"]["parts"]) == 9 and "crate" in bpy.data.collections
    sx, sy, sz = gate["info"]["size_m"]
    assert 0.9 < sx < 1.1 and 0.6 < sy < 0.8 and 0.4 < sz < 0.6, gate["info"]["size_m"]
    g2, _ = run_script(skill_script("gauge-modeling", "build_prop.py"), name="crate", max_ngons=100)
    assert len(bpy.data.collections["crate"].objects) == 9, "rebuild must replace, not append"


@test
def mesh_gate_reports_and_fix_repairs():
    sc = fresh()
    bad = mesh_obj("Bad", [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0), (7, 7, 7)], [(0, 1, 2)])
    g, _ = run_script(skill_script("gauge-modeling", "mesh_gate.py"), collection="Bad")
    assert not g[0]["pass"] and {"duplicate_verts", "loose_verts"} <= set(g[0]["failed"]), g[0]["failed"]
    dry, _ = run_script(skill_script("gauge-modeling", "fix_mesh.py"), collection="Bad")
    assert dry[0]["info"]["applied"] is False and len(bad.data.vertices) == 5
    steps = {f["step"] for f in dry[0]["info"]["fixes"]}
    assert {"merge", "loose"} <= steps, steps
    run_script(skill_script("gauge-modeling", "fix_mesh.py"), collection="Bad", apply=True)
    g2, _ = run_script(skill_script("gauge-modeling", "mesh_gate.py"), collection="Bad")
    assert g2[0]["pass"], g2[0]["failed"]
    assert len(bad.data.vertices) == 3


@test
def fix_mesh_flips_inverted_and_triangulates():
    fresh()
    ob = cube("In")
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    assert gauge.mesh_stats(ob)["inverted"]
    run_script(skill_script("gauge-modeling", "fix_mesh.py"), collection="In", apply=True)
    assert not gauge.mesh_stats(ob)["inverted"]
    ng = mesh_obj("Ng", [(0, 0, 0), (1, 0, 0), (1.5, 1, 0), (0.5, 1.6, 0), (-0.5, 1, 0)], [(0, 1, 2, 3, 4)])
    run_script(skill_script("gauge-modeling", "fix_mesh.py"), collection="Ng", apply=True, steps=["triangulate_ngons"])
    assert gauge.mesh_stats(ng)["ngons"] == 0 and gauge.mesh_stats(ng)["faces"] == 3


@test
def mesh_gate_limits_are_opt_in():
    fresh()
    ng = mesh_obj("Ng", [(0, 0, 0), (1, 0, 0), (1.5, 1, 0), (0.5, 1.6, 0), (-0.5, 1, 0)], [(0, 1, 2, 3, 4)])
    g, _ = run_script(skill_script("gauge-modeling", "mesh_gate.py"), collection="Ng")
    assert "ngons" not in g[0]["failed"]
    g, _ = run_script(skill_script("gauge-modeling", "mesh_gate.py"), collection="Ng", max_ngons=0)
    assert "ngons" in g[0]["failed"]
    g, _ = run_script(skill_script("gauge-modeling", "mesh_gate.py"), collection="Missing")
    assert "meshes_found" in g[0]["failed"]


run()
