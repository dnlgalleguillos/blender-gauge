import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import math

S = lambda n: skill_script("gauge-light-render", n)


def subject_scene():
    sc = fresh()
    col = bpy.data.collections.new("Subject")
    sc.collection.children.link(col)
    cube("crate", 1.0, (0, 0, 0.5), collection=col)
    sc.render.resolution_x, sc.render.resolution_y = 320, 180
    return sc


@test
def camera_framing_hits_the_requested_fill():
    sc = subject_scene()
    for fill in (0.3, 0.55):
        g, _ = run_script(S("frame_camera.py"), subject="Subject", lens=85, azimuth=25, elevation=18, fill=fill)
        gate = g[0]
        assert gate["gate"] == "camera-framing" and gate["pass"], gate["failed"]
        f = gauge.framing(sc, sc.camera, gauge.pick("Subject"))
        assert abs(f["fit"] - fill) < 0.01, (fill, f)
        assert f["margin"] > 0 and not f["behind_camera"]
    assert sc.camera.name == "gauge_cam" and len([o for o in bpy.data.objects if o.type == "CAMERA"]) == 1
    assert sc.camera.data.lens == 85
    d = (sc.camera.location - Vector((0, 0, 0.5))).length
    assert abs(d - gate["info"]["distance_m"]) < 1e-3


from mathutils import Vector  # noqa: E402


@test
def tight_framing_keeps_a_margin():
    sc = subject_scene()
    g, _ = run_script(S("frame_camera.py"), subject="Subject", lens=50, azimuth=35, elevation=25, fill=0.95)
    f = gauge.framing(sc, sc.camera, gauge.pick("Subject"))
    assert f["margin"] >= 0.019 and g[0]["info"]["distance_m"] > 1, f


@test
def camera_looks_at_subject_from_the_requested_side():
    sc = subject_scene()
    run_script(S("frame_camera.py"), subject="Subject", azimuth=90, elevation=0, fill=0.4)
    loc = sc.camera.location
    assert loc.x > 1.0 and abs(loc.y) < 1e-3 and abs(loc.z - 0.5) < 1e-3, tuple(loc)  # +X side, same height
    run_script(S("frame_camera.py"), subject="Subject", azimuth=0, elevation=90 - 1, fill=0.4)
    assert sc.camera.location.z > 2.0


@test
def dof_is_optional_and_focused():
    sc = subject_scene()
    run_script(S("frame_camera.py"), subject="Subject", aperture=2.0)
    assert sc.camera.data.dof.use_dof and sc.camera.data.dof.aperture_fstop == 2.0
    expect = (sc.camera.location - Vector((0, 0, 0.5))).length
    assert abs(sc.camera.data.dof.focus_distance - expect) < 1e-3
    run_script(S("frame_camera.py"), subject="Subject")
    assert not sc.camera.data.dof.use_dof


@test
def rig_scales_with_the_subject_and_hides_lights():
    sc = subject_scene()
    g, _ = run_script(S("rig.py"), subject="Subject", preset="three_point")
    gate = g[0]
    assert gate["pass"], gate["failed"]
    lights = [o for o in bpy.data.collections["gauge_rig"].objects if o.type == "LIGHT"]
    assert [o.name for o in lights] == ["rig_key", "rig_fill", "rig_rim"]
    assert not any(o.visible_camera for o in lights)
    R = gate["info"]["subject_radius_m"]
    key = bpy.data.objects["rig_key"]
    assert abs((key.location - Vector((0, 0, 0.5))).length - 3.4 * R) < 1e-3
    assert gate["info"]["ratio_key_fill"] > 2.0
    e_small = key.data.energy
    # a subject twice as big gets lights twice as far, four times the power (inverse square)
    bpy.data.objects["crate"].scale = (2, 2, 2)
    bpy.context.view_layer.update()
    run_script(S("rig.py"), subject="Subject", preset="three_point")
    assert abs(bpy.data.objects["rig_key"].data.energy / e_small - 4.0) < 0.05
    assert len([o for o in bpy.data.objects if o.name.startswith("rig_key")]) == 1, "rebuild must replace the rig"


@test
def every_preset_builds_and_ground_sits_under_subject():
    sc = subject_scene()
    for p in ("three_point", "softbox_product", "dramatic", "overcast"):
        g, _ = run_script(S("rig.py"), subject="Subject", preset=p, ground=True)
        assert g[0]["pass"], (p, g[0]["failed"])
    ground = bpy.data.objects["rig_ground"]
    assert abs(ground.location.z - 0.0) < 1e-4, ground.location
    run_script(S("rig.py"), subject="Subject", preset="three_point", ground=True, ground_color="#ff0000")
    base = bpy.data.materials["rig_ground_mat"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value
    assert base[0] > 0.9 and base[1] < 0.01, tuple(base)
    assert sc.world.name == "gauge_world"
    try:
        run_script(S("rig.py"), preset="nope")
        raise AssertionError("expected KeyError")
    except KeyError as e:
        assert "three_point" in str(e)


@test
def render_presets_change_settings_and_gate():
    sc = subject_scene()
    g, _ = run_script(S("render_preset.py"), preset="final")
    assert g[0]["pass"] and sc.cycles.samples == 256 and sc.render.resolution_percentage == 100
    g, _ = run_script(S("render_preset.py"), preset="draft", resolution=[640, 360])
    assert sc.cycles.samples == 16 and sc.render.resolution_percentage == 50 and g[0]["info"]["output_px"] == [320, 180]
    sc.cycles.samples = 2
    sc.cycles.use_denoising = False
    g, _ = run_script(S("render_preset.py"), apply=False)
    assert not g[0]["pass"] and "denoising_on" in g[0]["failed"]
    g, _ = run_script(S("render_preset.py"), preset="draft", look="Totally Fake Look")
    assert any("rejected" in n for n in g[0]["info"]["notes"])


@test
def render_check_judges_a_lit_scene_and_a_dark_one():
    sc = subject_scene()
    run_script(S("frame_camera.py"), subject="Subject", lens=70, azimuth=30, elevation=22, fill=0.35)
    run_script(S("rig.py"), subject="Subject", preset="three_point", ground=True)
    out = os.path.join(os.environ.get("TMPDIR", "/tmp"), "gauge_rc.png")
    g, _ = run_script(S("render_check.py"), subject="Subject", out=out, samples=8, percent=40, min_contrast=0.15)
    gate = g[0]
    st = gate["info"]["image"]
    assert os.path.getsize(out) > 1000
    assert gate["pass"], ([c for c in gate["checks"] if not c["ok"]], st)
    # kill every light and the world: the gate must say it is too dark
    for o in list(bpy.data.collections["gauge_rig"].objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    g2, _ = run_script(S("render_check.py"), subject="Subject", out=out, samples=4, percent=30)
    assert not g2[0]["pass"] and "mean_luma" in g2[0]["failed"], g2[0]["failed"]


@test
def framing_gate_catches_a_cropped_subject():
    sc = subject_scene()
    run_script(S("frame_camera.py"), subject="Subject", fill=0.4)
    sc.camera.location.x += 6
    bpy.context.view_layer.update()
    out = os.path.join(os.environ.get("TMPDIR", "/tmp"), "gauge_crop.png")
    g, _ = run_script(S("render_check.py"), subject="Subject", out=out, samples=2, percent=20)
    assert "subject_inside_frame_margin" in g[0]["failed"]


@test
def turntable_loops_at_constant_speed():
    sc = subject_scene()
    run_script(S("frame_camera.py"), subject="Subject", fill=0.4, azimuth=0)
    start = sc.camera.matrix_world.translation.copy()
    g, _ = run_script(S("turntable.py"), subject="Subject", frames=48, fps=24)
    gate = g[0]
    assert gate["pass"], [c for c in gate["checks"] if not c["ok"]]
    assert sc.frame_start == 1 and sc.frame_end == 48 and gate["info"]["seconds"] == 2.0
    piv = bpy.data.objects["gauge_pivot"]
    sc.frame_set(1)
    bpy.context.view_layer.update()
    p1 = sc.camera.matrix_world.translation.copy()
    assert (p1 - start).length < 1e-3, "frame 1 must keep the framed shot"
    sc.frame_set(25)  # halfway: opposite side of the subject
    bpy.context.view_layer.update()
    p2 = sc.camera.matrix_world.translation
    centre = Vector((0, 0, 0.5))
    assert abs((p2 - centre).length - (start - centre).length) < 1e-3, "orbit radius must stay constant"
    assert abs(p2.y - (2 * centre.y - start.y)) < 5e-2 and abs(p2.x) < 5e-2, (tuple(p2), tuple(start))


run()
