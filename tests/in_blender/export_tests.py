import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

S = lambda n: skill_script("gauge-export", n)
TMP = os.environ.get("TMPDIR", "/tmp")


def prop():
    fresh()
    sys.path.insert(0, os.path.join(ROOT, "skills", "gauge-materials", "scripts"))
    import presets
    run_script(skill_script("gauge-modeling", "build_prop.py"), name="crate", max_ngons=100)
    for o in bpy.data.collections["crate"].objects:
        o.data.materials.append(presets.make("mat_crate", "plastic", "#aa5522"))
    return gauge.pick("crate")


def counts():
    return {c: len(getattr(bpy.data, c)) for c in ("objects", "meshes", "materials", "images", "collections")}


@test
def every_format_round_trips():
    objs = prop()
    src_size = sorted(gauge.size_of(objs))
    for ext in (".glb", ".gltf", ".fbx", ".obj", ".stl", ".usdc", ".ply"):
        out = os.path.join(TMP, "gauge_exp", "crate" + ext)
        before = counts()
        g, _ = run_script(S("export.py"), out=out, objects="crate")
        gate = g[0]
        assert gate["pass"], (ext, [c for c in gate["checks"] if not c["ok"]])
        assert gate["info"]["bytes"] > 500 and os.path.exists(out), ext
        assert counts() == before, (ext, before, counts())
        rt = gate["info"]["roundtrip"]
        assert rt["triangles"] == gate["info"]["triangles"], (ext, rt)


@test
def budgets_fail_with_a_hint():
    prop()
    out = os.path.join(TMP, "gauge_exp", "tiny.glb")
    g, _ = run_script(S("export.py"), out=out, objects="crate", max_tris=100, max_objects=2)
    assert not g[0]["pass"] and {"triangles_budget", "object_count_budget"} <= set(g[0]["failed"]), g[0]["failed"]
    assert "decimate" in next(c["hint"] for c in g[0]["checks"] if c["name"] == "triangles_budget")
    g, _ = run_script(S("export.py"), out=out, objects="crate", budget="mobile")
    assert g[0]["pass"]


@test
def big_textures_are_flagged():
    objs = prop()
    img = bpy.data.images.new("huge_albedo", 4096, 4096)
    mat = bpy.data.materials["mat_crate"]
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    g, _ = run_script(S("export.py"), out=os.path.join(TMP, "gauge_exp", "tex.glb"), objects="crate", budget="web", verify=False)
    assert "texture_size_budget" in g[0]["failed"], g[0]["failed"]
    bad = next(c for c in g[0]["checks"] if c["name"] == "texture_size_budget")
    assert "huge_albedo 4096x4096" in bad["value"][0]


@test
def selection_is_restored_and_only_chosen_objects_leave():
    objs = prop()
    other = cube("not_exported", 5.0, (20, 0, 0))
    bpy.context.view_layer.update()  # new objects get their selection state when the view layer syncs
    other.select_set(True)
    objs[0].select_set(False)
    assert other.select_get() and not objs[0].select_get()
    out = os.path.join(TMP, "gauge_exp", "only.glb")
    g, _ = run_script(S("export.py"), out=out, objects="crate")
    assert other.select_get() and not objs[0].select_get(), "selection must be restored"
    sx = max(g[0]["info"]["roundtrip"]["size_m"])
    assert sx < 2.0, "the 5 m cube must not be in the file"


@test
def unknown_things_are_reported_not_raised():
    prop()
    g, _ = run_script(S("export.py"), out="/tmp/x.abc")
    assert not g[0]["pass"] and g[0]["failed"] == ["format_known"]
    g, _ = run_script(S("export.py"), out=os.path.join(TMP, "gauge_exp", "n.glb"), objects="Missing")
    assert g[0]["failed"] == ["objects_found"]
    try:
        run_script(S("export.py"), out="/tmp/x.glb", budget="huge")
        raise AssertionError("expected KeyError")
    except KeyError as e:
        assert "web" in str(e)


run()
