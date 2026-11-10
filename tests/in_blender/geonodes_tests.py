import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import json

REC = os.path.join(ROOT, "skills", "gauge-geonodes", "recipes")


def make(recipe, **inputs):
    g, _ = run_script(skill_script("gauge-geonodes", "gn_make.py"), recipe=recipe, host=f"{recipe}_host", inputs=inputs)
    return g[0]


@test
def height_grid_builds_and_counts_instances():
    fresh()
    g = make("height_grid", **{"Res X": 20, "Res Y": 15})
    assert g["gate"] == "geonodes-make" and g["pass"], [c for c in g["checks"] if not c["ok"]]
    assert g["info"]["instances"] == 300, g["info"]
    host = bpy.data.objects["height_grid_host"]
    sx, sy, sz = g["info"]["size_m"]
    assert 4.9 < sx < 5.2 and 3.9 < sy < 4.2 and 0.2 < sz < 0.5, g["info"]["size_m"]
    src = bpy.data.objects["height_grid_source"]
    assert src.hide_render and gauge.instance_count(host) == 300, "hiding the source must not remove instances"


@test
def inputs_change_the_result():
    fresh()
    make("height_grid", **{"Res X": 12, "Res Y": 10})
    host = bpy.data.objects["height_grid_host"]
    mod = host.modifiers["height_grid"]
    flat = gauge.size_of([host])[2]
    gauge.gn_set(mod, Amplitude=1.2)
    bpy.context.view_layer.update()
    tall = gauge.size_of([host])[2]
    assert tall > flat * 2.5, (flat, tall)
    gauge.gn_set(mod, **{"Res X": 30})
    bpy.context.view_layer.update()
    assert gauge.instance_count(host) == 300


@test
def smoothness_is_measurable():
    fresh()
    make("height_grid", **{"Res X": 40, "Res Y": 30, "Amplitude": 0.4})
    host = bpy.data.objects["height_grid_host"]
    mod = host.modifiers["height_grid"]
    ok, _ = run_script(skill_script("gauge-geonodes", "gn_gate.py"), object=host.name, min_instances=1000, max_neighbour_step=0.3)
    assert ok[0]["pass"], [c for c in ok[0]["checks"] if not c["ok"]]
    g1 = ok[0]["info"]["objects"][host.name]["grid"]
    assert g1["grid"] == [40, 30] and g1["cells"] == 1200 and g1["max_step"] > 0.01, g1
    gauge.gn_set(mod, Amplitude=0.8)  # heights are linear in Amplitude, so every step doubles
    bpy.context.view_layer.update()
    g2 = gauge.grid_step(gauge.instance_positions(host))
    assert abs(g2["mean_step"] / g1["mean_step"] - 2.0) < 0.05, (g1, g2)
    gauge.gn_set(mod, Amplitude=0.0)
    bpy.context.view_layer.update()
    assert gauge.grid_step(gauge.instance_positions(host))["max_step"] < 1e-6
    gauge.gn_set(mod, Amplitude=0.8)
    bpy.context.view_layer.update()
    bad, _ = run_script(skill_script("gauge-geonodes", "gn_gate.py"), object=host.name, max_neighbour_step=g1["max_step"])
    assert not bad[0]["pass"] and "height_grid_host: neighbour_step" in bad[0]["failed"], bad[0]["failed"]


@test
def radial_array_places_copies_on_a_circle():
    fresh()
    g = make("radial_array", Count=8, Radius=2.0)
    assert g["pass"] and g["info"]["instances"] == 8, g["info"]
    host = bpy.data.objects["radial_array_host"]
    pts = gauge.instance_positions(host)
    import math
    radii = [math.hypot(p[0], p[1]) for p in pts]
    assert all(abs(r - 2.0) < 1e-4 for r in radii), radii
    assert len({(round(p[0], 3), round(p[1], 3)) for p in pts}) == 8


@test
def scatter_surface_respects_density_and_seed():
    fresh()
    g = make("scatter_surface", Density=50.0, Seed=3)
    assert g["pass"], [c for c in g["checks"] if not c["ok"]]
    n1 = g["info"]["instances"]
    assert n1 > 20, n1
    host = bpy.data.objects["scatter_surface_host"]
    mod = host.modifiers["scatter_surface"]
    gauge.gn_set(mod, Density=200.0)
    bpy.context.view_layer.update()
    n2 = gauge.instance_count(host)
    assert n2 > n1 * 2.5, (n1, n2)
    p_a = gauge.instance_positions(host)
    gauge.gn_set(mod, Seed=9)
    bpy.context.view_layer.update()
    assert gauge.instance_positions(host) != p_a, "a different seed must move the points"


@test
def rebuild_is_idempotent():
    fresh()
    make("radial_array", Count=6)
    make("radial_array", Count=10)
    assert len([g for g in bpy.data.node_groups if g.name.startswith("radial_array")]) == 1
    host = bpy.data.objects["radial_array_host"]
    assert len([m for m in host.modifiers if m.type == "NODES"]) == 1
    assert gauge.instance_count(host) == 10


@test
def gate_reports_empty_and_broken_trees():
    fresh()
    make("radial_array", Count=6)
    host = bpy.data.objects["radial_array_host"]
    host.modifiers["radial_array"].node_group.links.clear()
    bpy.context.view_layer.update()
    g, _ = run_script(skill_script("gauge-geonodes", "gn_gate.py"), object=host.name)
    assert not g[0]["pass"]
    assert "radial_array: group_output_connected" in g[0]["failed"] and f"{host.name}: not_empty" in g[0]["failed"]
    g, _ = run_script(skill_script("gauge-geonodes", "gn_gate.py"), object="nothing")
    assert False if g and g[0]["pass"] else True


@test
def dump_reads_back_a_group():
    fresh()
    make("radial_array", Count=6)
    out = os.path.join(os.environ.get("TMPDIR", "/tmp"), "gauge_dump.json")
    g, text = run_script(skill_script("gauge-geonodes", "gn_dump.py"), group="radial_array", out=out)
    assert g[0]["pass"] and "turn [Math]" in text
    spec = json.load(open(out))
    assert {"ring", "inst", "gin"} <= set(spec["nodes"]) and spec["interface"]["inputs"][1] == {"name": "Count", "type": "Int"}
    again = gauge.gn_make("rebuilt", spec)
    host = bpy.data.objects["radial_array_host"]
    host.modifiers.new("again", "NODES").node_group = again
    gauge.gn_set(host.modifiers["again"], Count=5, Instance="radial_array_instance")
    bpy.context.view_layer.update()
    assert gauge.instance_count(host) >= 5


run()
