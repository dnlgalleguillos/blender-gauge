import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

SK = os.path.join(ROOT, "skills", "gauge-materials", "scripts")
sys.path.insert(0, SK)
import presets  # noqa: E402


@test
def every_preset_builds_and_passes_node_gate():
    fresh()
    for nm in presets.PRESETS:
        mat = presets.make(f"mat_{nm}", nm)
        r = gauge.Report(nm)
        gauge.node_gate(r, mat.node_tree, nm)
        hard = [c for c in r.failed()]
        assert not hard, (nm, hard)
        ids = {n.bl_idname for n in mat.node_tree.nodes}
        assert "ShaderNodeBsdfPrincipled" in ids and "ShaderNodeOutputMaterial" in ids


@test
def presets_apply_color_and_overrides():
    fresh()
    m = presets.make("c", "plastic", "#336699", Roughness=0.7)
    bsdf = m.node_tree.nodes["bsdf"]
    got = gauge.linear_to_hex(bsdf.inputs["Base Color"].default_value[:3])
    assert got == "#336699", got
    assert abs(bsdf.inputs["Roughness"].default_value - 0.7) < 1e-6
    try:
        presets.make("x", "nope")
        raise AssertionError("expected KeyError")
    except KeyError as e:
        assert "metal" in str(e)


@test
def rebuild_keeps_users():
    fresh()
    ob = cube("Housing", 1.0)
    run_script(skill_script("gauge-materials", "make_material.py"), name="mat_a", preset="metal", assign_to="Housing")
    mat = bpy.data.materials["mat_a"]
    assert ob.data.materials[0] == mat
    run_script(skill_script("gauge-materials", "make_material.py"), name="mat_a", preset="plastic", color="#aa0000")
    assert bpy.data.materials["mat_a"] is mat and ob.data.materials[0] is mat
    assert abs(mat.node_tree.nodes["bsdf"].inputs["Metallic"].default_value) < 1e-6
    assert [m.name for m in bpy.data.materials].count("mat_a") == 1


@test
def dump_of_preset_round_trips():
    fresh()
    m = presets.make("wood", "wood")
    d = gauge.node_dump(m.node_tree)
    m2 = bpy.data.materials.new("wood2")
    gauge.node_build(m2.node_tree, d)
    d2 = gauge.node_dump(m2.node_tree)
    strip = lambda x: {k: {a: b for a, b in v.items() if a != "at"} for k, v in x["nodes"].items()}
    assert strip(d) == strip(d2)
    assert sorted(d["links"]) == sorted(d2["links"])
    assert "rings [TexWave]" in gauge.node_text(m.node_tree)


@test
def material_gate_flags_pbr_mistakes():
    fresh()
    ob = cube("Thing")
    good = presets.make("good", "plastic", "#c8352b")
    ob.data.materials.append(good)
    g, _ = run_script(skill_script("gauge-materials", "material_gate.py"), collection="Thing")
    assert g[0]["pass"] and not [c for c in g[0]["checks"] if not c["ok"]], g[0]["checks"]
    bad = bpy.data.materials.new("bad")
    b = bad.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (1, 1, 1, 1)
    b.inputs["Metallic"].default_value = 0.5
    b.inputs["Roughness"].default_value = 0.0
    ob.data.materials[0] = bad
    ob.data.materials.append(None)
    g, _ = run_script(skill_script("gauge-materials", "material_gate.py"), collection="Thing")
    warn = {c["name"] for c in g[0]["checks"] if not c["ok"] and c.get("severity") == "warn"}
    assert {"bad: metallic_binary", "bad: roughness_floor", "empty_material_slots"} <= warn, warn
    img = bpy.data.images.new("rough_map", 4, 4)
    img.colorspace_settings.name = "sRGB"
    tex = bad.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    bad.node_tree.links.new(tex.outputs["Color"], b.inputs["Roughness"])
    g, _ = run_script(skill_script("gauge-materials", "material_gate.py"), collection="Thing")
    assert "bad: data_textures_non_color" in g[0]["failed"] and not g[0]["pass"]


@test
def swatch_sheet_renders_distinct_swatches():
    fresh()
    leftover = cube("UserCube", 3.0)  # an object of the user's: must not leak into the sheet or be touched
    before = sorted(o.name for o in bpy.data.objects)
    out = os.path.join(os.environ.get("TMPDIR", "/tmp"), "gauge_swatch_test.png")
    if os.path.exists(out):
        os.remove(out)
    g, _ = run_script(skill_script("gauge-materials", "swatch_sheet.py"), out=out, samples=6, percent=30)
    gate = g[0]
    assert os.path.getsize(out) > 2000, "no image"
    assert not any(c["name"].endswith("inside_frame") and not c["ok"] for c in gate["checks"]), gate["checks"]
    assert gate["pass"], [c for c in gate["checks"] if not c["ok"]]
    assert "gauge_swatches" not in bpy.data.collections and "gauge_swatch_scene" not in bpy.data.scenes
    assert sorted(o.name for o in bpy.data.objects) == before, "the user's scene must be left exactly as it was"
    assert not [c for c in gate["checks"] if c["name"].endswith("not_occluded") and not c["ok"]]
    assert any(c["name"] == "area_lights_not_in_shot" and c["ok"] for c in gate["checks"])


run()
