import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

EX = os.path.join(ROOT, "examples", "wavy-cubes", "build_wavy.py")
TMP = os.environ.get("TMPDIR", "/tmp")


@test
def wavy_cubes_builds_and_passes_its_gates_small():
    fresh()
    out = os.path.join(TMP, "gauge_wavy_test.png")
    g, _ = run_script(EX, out=out, blend=os.path.join(TMP, "gauge_wavy_test.blend"), width=320, height=180, samples=6, res=40,
                      size_x=1.7, size_y=1.7, distance=0.9, ahead=0.2)
    gate = g[0]
    assert gate["gate"] == "wavy-cubes" and os.path.getsize(out) > 2000
    hard = [c for c in gate["checks"] if not c["ok"] and c.get("severity") != "warn"]
    assert not hard or {c["name"] for c in hard} <= {"cubes_across_frame_at_focus", "grid_edge_not_visible"}, hard
    assert gate["info"]["instances"] == 1600 and gate["info"]["grid"]["grid"] == [40, 40]
    assert gate["info"]["look"] is not None


@test
def wavy_cubes_scan_measures_without_rendering_and_detects_rough_noise():
    fresh()
    smooth, _ = run_script(EX, scan=True, render=False, res=60, size_x=2.5, size_y=2.5, blend=os.path.join(TMP, "gw1.blend"))
    st_smooth = smooth[0]["info"]["grid"]
    assert st_smooth["cells"] == 3600 and st_smooth["max_step"] < 0.08, st_smooth
    fresh()
    rough, _ = run_script(EX, scan=True, render=False, res=60, size_x=2.5, size_y=2.5, roughness=1.0, detail=15.0,
                          blend=os.path.join(TMP, "gw2.blend"))
    st_rough = rough[0]["info"]["grid"]
    assert st_rough["max_step"] > st_smooth["max_step"] * 1.5, (st_smooth, st_rough)
    assert "camera" not in rough[0]["info"], "scan mode must stop before camera and render"


@test
def example_edge_gate_catches_a_grid_that_is_too_small():
    fresh()
    g, _ = run_script(EX, render=False, res=30, size_x=0.9, size_y=0.9, blend=os.path.join(TMP, "gw3.blend"))
    assert "grid_edge_not_visible" in g[0]["failed"], g[0]["failed"]


run()
