import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import numpy as np

S = lambda n: skill_script("gauge-reference", n)
TMP = os.environ.get("TMPDIR", "/tmp")


def save_png(name, arr):
    img = bpy.data.images.new(name, arr.shape[1], arr.shape[0])
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).astype(np.float32).ravel())
    img.filepath_raw = os.path.join(TMP, name + ".png")
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return os.path.join(TMP, name + ".png")


def scene_image(w=96, h=64):
    a = np.zeros((h, w, 4), np.float32)
    a[..., 3] = 1
    yy, xx = np.mgrid[0:h, 0:w]
    a[..., 0] = 0.25 + 0.5 * xx / w
    a[..., 1] = 0.2 + 0.3 * yy / h
    a[..., 2] = 0.35
    a[20:40, 30:60, :3] = [0.8, 0.5, 0.1]
    return a


def lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def srgb(a):
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(np.maximum(a, 1e-9), 1 / 2.4) - 0.055)


@test
def report_describes_an_image_and_its_distance():
    fresh()
    ref = scene_image()
    p_ref = save_png("ref_a", ref)
    g, _ = run_script(S("ref_report.py"), image=p_ref)
    info = g[0]["info"]
    assert g[0]["pass"] and info["image"]["size"] == [96, 64] and 0.2 < info["image"]["mean_luma"] < 0.6
    assert len(info["image"]["palette"]) >= 2 and len(info["sharpness_grid"]) == 4
    g, _ = run_script(S("ref_report.py"), image=p_ref, reference=p_ref)
    d = g[0]["info"]["delta"]
    assert d["mean_abs_error"] < 0.005 and abs(d["exposure_stops"]) < 0.01 and d["luma_correlation"] > 0.999, d


@test
def match_gate_says_what_to_change_in_stops():
    fresh()
    ref = scene_image()
    p_ref = save_png("ref_b", ref)
    same, _ = run_script(S("ref_match.py"), image=p_ref, reference=p_ref)
    assert same[0]["pass"], same[0]["failed"]
    bright = ref.copy()
    bright[..., :3] = np.clip(srgb(lin(ref[..., :3]) * 2.0), 0, 1)  # exactly one stop more light
    p_b = save_png("mine_bright", bright)
    g, _ = run_script(S("ref_match.py"), image=p_b, reference=p_ref, max_exposure=0.2)
    assert not g[0]["pass"] and "exposure_stops" in g[0]["failed"], g[0]["failed"]
    st = g[0]["info"]["delta"]["exposure_stops"]
    assert 0.85 < st < 1.15, st
    hint = next(c["hint"] for c in g[0]["checks"] if c["name"] == "exposure_stops")
    assert "brighter" in hint and "multiply every light" in hint and any(x in hint for x in ("0.5", "0.4", "0.6")), hint
    tinted = ref.copy()
    tinted[..., 0] = np.clip(tinted[..., 0] + 0.12, 0, 1)
    g, _ = run_script(S("ref_match.py"), image=save_png("mine_red", tinted), reference=p_ref, max_exposure=1.0)
    assert "tint_red" in g[0]["failed"] and "too much red" in next(c["hint"] for c in g[0]["checks"] if c["name"] == "tint_red")
    flat = ref.copy()
    flat[..., :3] = 0.5 + (flat[..., :3] - 0.5) * 0.4
    g, _ = run_script(S("ref_match.py"), image=save_png("mine_flat", flat), reference=p_ref, max_exposure=1.0)
    assert "contrast_ratio" in g[0]["failed"]


@test
def colors_are_read_at_points():
    fresh()
    a = np.zeros((40, 60, 4), np.float32)
    a[..., 3] = 1
    a[:, :30, :3] = [0.2, 0.4, 0.6]
    a[:, 30:, :3] = [0.9, 0.1, 0.1]
    p = save_png("ref_c", a)
    g, _ = run_script(S("ref_colors.py"), image=p, points=[[0.25, 0.5], [45, 20], [0.9, 0.1]], radius=2)
    s = g[0]["info"]["samples"]
    assert s[0]["srgb_hex"] == "#336699" and s[1]["srgb_hex"] == "#e61a1a" and s[2]["srgb_hex"] == "#e61a1a", s
    assert abs(s[0]["linear"][0] - lin(np.float32(0.2))) < 0.01
    g, _ = run_script(S("ref_colors.py"), image=p, points=[[500, 500]])
    assert not g[0]["pass"]


@test
def node_text_reads_materials_and_groups():
    fresh()
    sys.path.insert(0, os.path.join(ROOT, "skills", "gauge-materials", "scripts"))
    import presets
    presets.make("steel", "brushed_metal")
    g, text = run_script(S("node_text.py"), material="steel")
    assert g[0]["pass"] and "streaks [TexNoise]" in text and "<- ramp.Result" in text, text
    out = os.path.join(TMP, "steel_spec.json")
    run_script(S("node_text.py"), material="steel", spec=out)
    import json
    spec = json.load(open(out))
    assert "bsdf" in spec["nodes"] and ["bsdf.BSDF", "out.Surface"] in spec["links"]
    g, _ = run_script(S("node_text.py"), material="nope")
    assert not g[0]["pass"] and "material_exists" in g[0]["failed"]


@test
def workspace_begin_end_restores_and_confirms():
    sc = fresh()
    cam = camera_at()
    w0 = bpy.data.worlds.new("OrigWorld")
    sc.world = w0
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 1280
    run_script(S("workspace.py"), action="begin", name="match1")
    assert "match1" in bpy.data.collections and "gauge_prev" in sc
    # work happens: new camera, world, engine, an object in the workspace
    cam2 = bpy.data.objects.new("MatchCam", bpy.data.cameras.new("MatchCam"))
    bpy.data.collections["match1"].objects.link(cam2)
    sc.camera = cam2
    sc.world = bpy.data.worlds.new("MatchWorld")
    sc.render.engine = "CYCLES"
    sc.render.resolution_x = 320
    keep = cube("keep_me", 1.0)  # lives outside the workspace
    cube("scratch", 1.0, collection=bpy.data.collections["match1"])
    g, _ = run_script(S("workspace.py"), action="end", name="match1")
    assert sc.camera == cam and sc.world == w0 and sc.render.engine == "BLENDER_EEVEE" and sc.render.resolution_x == 1280
    assert "gauge_prev" not in sc
    assert "match1" in bpy.data.collections and "scratch" in bpy.data.objects, "dry run must not delete"
    assert sorted(g[0]["info"]["removal"]["objects"]) == ["MatchCam", "scratch"]
    run_script(S("workspace.py"), action="end", name="match1", confirm=True)
    assert "match1" not in bpy.data.collections and "scratch" not in bpy.data.objects and "keep_me" in bpy.data.objects


run()
