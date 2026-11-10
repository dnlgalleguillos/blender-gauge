import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *


@test
def gate_passes_on_tidy_scene():
    sc = fresh()
    col = bpy.data.collections.new("Props")
    sc.collection.children.link(col)
    cube("crate", 1.0, (0, 0, 0.5), collection=col)
    cam = camera_at()
    sc.collection.objects.unlink(cam)
    col.objects.link(cam)
    g, _ = run_script(skill_script("gauge-scene", "scene_gate.py"))
    assert g[0]["gate"] == "scene-hygiene" and g[0]["pass"], g[0]["failed"]
    assert not [c for c in g[0]["checks"] if not c["ok"]], g[0]["checks"]


@test
def gate_catches_units_and_scale():
    sc = fresh()
    sc.unit_settings.scale_length = 0.01
    ob = cube("Cube")
    ob.scale = (-1, 1, 1)
    g, _ = run_script(skill_script("gauge-scene", "scene_gate.py"))
    bad = set(g[0]["failed"])
    assert {"unit_scale", "negative_scale"} <= bad, bad
    warn = {c["name"] for c in g[0]["checks"] if not c["ok"] and c.get("severity") == "warn"}
    assert "default_object_names" in warn


@test
def tidy_is_dry_run_by_default():
    sc = fresh()
    sc.unit_settings.scale_length = 0.5
    ob = cube("Part", 1.0)
    ob.scale = (2, 2, 2)
    g, _ = run_script(skill_script("gauge-scene", "tidy.py"))
    info = g[0]["info"]
    assert info["applied"] is False and len(info["actions"]) >= 3, info
    assert sc.unit_settings.scale_length == 0.5 and ob.scale[0] == 2


@test
def tidy_applies_scale_units_collections():
    sc = fresh()
    sc.unit_settings.scale_length = 0.5
    a = cube("A", 1.0)
    a.scale = (2, 3, 4)
    shared = cube("B", 1.0, (5, 0, 0))
    shared2 = bpy.data.objects.new("B2", shared.data)
    sc.collection.objects.link(shared2)
    shared.scale = (2, 2, 2)
    parent = cube("P", 1.0, (9, 0, 0))
    child = cube("C", 1.0, (9, 0, 2))
    child.parent = parent
    parent.scale = (3, 3, 3)
    g, _ = run_script(skill_script("gauge-scene", "tidy.py"), apply=True)
    info = g[0]["info"]
    assert sc.unit_settings.scale_length == 1.0
    assert tuple(a.scale) == (1, 1, 1) and gauge.size_of([a]) == (2.0, 3.0, 4.0), gauge.size_of([a])
    assert tuple(shared.scale) == (2, 2, 2), "shared mesh data must be skipped"
    assert tuple(parent.scale) == (3, 3, 3), "parent with children must be skipped"
    assert any("shares mesh" in s for s in info["skipped"]) and any("children" in s for s in info["skipped"])
    assert a.users_collection[0].name == "Meshes" and "Meshes" in sc.collection.children
    g2, _ = run_script(skill_script("gauge-scene", "scene_gate.py"))
    assert "unit_scale" not in g2[0]["failed"]


@test
def purge_only_removes_unused():
    sc = fresh()
    keep = bpy.data.materials.new("used")
    ob = cube("X")
    ob.data.materials.append(keep)
    bpy.data.materials.new("orphan")
    g, _ = run_script(skill_script("gauge-scene", "tidy.py"), steps=["purge"], apply=True)
    assert "orphan" not in bpy.data.materials and "used" in bpy.data.materials


run()
