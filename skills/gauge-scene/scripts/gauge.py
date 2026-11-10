"""gauge - measurement helpers shared by every Blender Gauge skill.

One file, only bpy / bmesh / mathutils / numpy (all bundled with Blender). Each skill keeps a synced copy
in its own scripts/ folder, so edit lib/gauge.py and run `python tools/sync_lib.py`.

The idea: do not trust that a change worked, measure it. Every check is a named number with a limit, the
whole run ends in one machine-readable line:

    GAUGE_JSON {"gate": "...", "pass": true, "checks": [...], "info": {...}}

Typical use inside a skill script:

    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gauge
    P = gauge.params(globals(), collection=None, max_ngons=0)
    r = gauge.Report("mesh-health")
    gauge.mesh_gate(r, gauge.pick(P["collection"]), max_ngons=P["max_ngons"])
    r.emit()

Parameters come from (lowest to highest priority): defaults, env GAUGE_PARAMS (JSON), SCRIPT_ARGS (the
blender-mcp run_blender_script `args`), and `key=value` words after `--` on the command line.
"""
import json
import math
import os
import re
import sys

import bpy
import bmesh
from mathutils import Vector

VERSION = "0.1.0"
MARK = "GAUGE_JSON "


# ----------------------------------------------------------------------------- report / params

def _coerce(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


def params(ns=None, **defaults):
    """Merge defaults < env GAUGE_PARAMS < SCRIPT_ARGS (from `ns`, usually globals()) < key=value after `--`."""
    p = dict(defaults)
    env = os.environ.get("GAUGE_PARAMS")
    if env:
        p.update(json.loads(env))
    if ns and isinstance(ns.get("SCRIPT_ARGS"), dict):
        p.update(ns["SCRIPT_ARGS"])
    argv = sys.argv
    if "--" in argv:
        for word in argv[argv.index("--") + 1:]:
            if "=" in word:
                k, v = word.split("=", 1)
                p[k] = _coerce(v)
    unknown = [k for k in p if k not in defaults and defaults]
    if unknown:
        p["_unknown"] = unknown
    return p


def _num(v):
    if isinstance(v, float):
        return round(v, 5)
    if isinstance(v, (list, tuple)):
        return [_num(x) for x in v]
    if isinstance(v, dict):
        return {k: _num(x) for k, x in v.items()}
    return v


class Report:
    """A named gate: a list of checks (name, value, limit, ok) plus free-form info."""

    def __init__(self, gate):
        self.gate = gate
        self.checks = []
        self.info = {}

    def check(self, name, value, ok, limit=None, hint=None, severity="error"):
        """severity 'error' fails the gate, 'warn' is listed but does not."""
        c = {"name": name, "value": _num(value), "ok": bool(ok)}
        if limit is not None:
            c["limit"] = _num(limit)
        if hint and not ok:
            c["hint"] = hint
        if severity != "error":
            c["severity"] = severity
        self.checks.append(c)
        return bool(ok)

    def le(self, name, value, limit, **kw):
        return self.check(name, value, value <= limit, f"<= {limit}", **kw)

    def ge(self, name, value, limit, **kw):
        return self.check(name, value, value >= limit, f">= {limit}", **kw)

    def eq(self, name, value, expect, tol=0.0, **kw):
        ok = abs(value - expect) <= tol if isinstance(value, (int, float)) else value == expect
        return self.check(name, value, ok, f"== {expect}" + (f" +-{tol}" if tol else ""), **kw)

    @property
    def ok(self):
        return all(c["ok"] or c.get("severity") == "warn" for c in self.checks)

    def failed(self):
        return [c for c in self.checks if not c["ok"] and c.get("severity") != "warn"]

    def data(self):
        return {"gate": self.gate, "pass": self.ok, "failed": [c["name"] for c in self.failed()],
                "checks": self.checks, "info": _num(self.info)}

    def emit(self):
        d = self.data()
        print(MARK + json.dumps(d, separators=(",", ":")))
        return d


def parse(output):
    """Pull every GAUGE_JSON line out of a captured stdout (for tests or the agent)."""
    return [json.loads(line[len(MARK):]) for line in output.splitlines() if line.startswith(MARK)]


# ----------------------------------------------------------------------------- selecting things

def pick(spec=None, mesh_only=True, visible=True):
    """Objects from a spec: None = whole scene, 'Name' = object or collection (recursive), list of names,
    '@selected' = current selection."""
    if spec in (None, "", "@scene"):
        found = list(bpy.context.scene.objects)
    elif spec == "@selected":
        found = list(bpy.context.selected_objects)
    elif isinstance(spec, (list, tuple)):
        found = []
        for s in spec:
            found += pick(s, mesh_only=False, visible=False)
    elif spec in bpy.data.collections:
        found = list(bpy.data.collections[spec].all_objects)
    elif spec in bpy.data.objects:
        found = [bpy.data.objects[spec]]
    else:
        found = []
    seen, out = set(), []
    for o in found:
        if o.name in seen:
            continue
        seen.add(o.name)
        if mesh_only and o.type != "MESH":
            continue
        if visible and (o.hide_render and o.hide_viewport):
            continue
        out.append(o)
    return out


def bounds(objs):
    """World-space (min, max) Vectors over the evaluated geometry, or None when empty. Objects that only produce
    Geometry Nodes instances are measured through those instances."""
    dg = bpy.context.evaluated_depsgraph_get()
    wanted = {o.name for o in objs}
    inst_pts, has_inst = [], set()
    for inst in dg.object_instances:  # instances are only valid inside this loop: read them right away
        if inst.is_instance and inst.parent and inst.parent.original.name in wanted:
            has_inst.add(inst.parent.original.name)
            m = inst.matrix_world
            inst_pts += [m @ Vector(c) for c in inst.object.bound_box]
    pts = list(inst_pts)
    for o in objs:
        if o.name in has_inst:
            continue
        try:
            e = o.evaluated_get(dg)
        except ValueError:  # object lives in a scene that is not the active one: use it as is
            e = o
        pts += [e.matrix_world @ Vector(c) for c in e.bound_box]
    if not pts:
        return None
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def size_of(objs):
    b = bounds(objs)
    return tuple(b[1] - b[0]) if b else (0.0, 0.0, 0.0)


# ----------------------------------------------------------------------------- scene hygiene

_DEFAULT_NAME = re.compile(r"^(Cube|Sphere|Plane|Cylinder|Cone|Torus|Circle|Grid|Suzanne|Monkey|Empty|"
                           r"Light|Point|Sun|Spot|Area|Camera|Curve|Text|Icosphere)(\.\d+)?$")
_DEFAULT_MAT = re.compile(r"^(Material|Material\.\d+|Dots Stroke|None)$")


def scene_gate(r, scene=None, expect_unit_scale=1.0, allow_default_names=False, allow_orphans=True):
    """Units, naming, transforms and collection hygiene of a scene."""
    sc = scene or bpy.context.scene
    us = sc.unit_settings
    r.check("unit_system", us.system, us.system == "METRIC", "METRIC", "Scene > Units > Metric")
    r.eq("unit_scale", us.scale_length, expect_unit_scale, 1e-6, hint="keep 1.0 so 1 BU = 1 m")
    objs = [o for o in sc.objects]
    in_master = [o.name for o in sc.collection.objects]
    r.check("objects_in_named_collections", len(in_master), len(in_master) == 0 or len(sc.collection.children) == 0,
            "0 loose in Scene Collection", "link objects to named collections", severity="warn")
    if not allow_default_names:
        bad = [o.name for o in objs if _DEFAULT_NAME.match(o.name)]
        r.check("default_object_names", bad[:8], not bad, "none", "rename to what the object is", severity="warn")
        badm = [m.name for m in bpy.data.materials if m.users and _DEFAULT_MAT.match(m.name)]
        r.check("default_material_names", badm[:8], not badm, "none", "name materials by purpose", severity="warn")
    unapplied = [o.name for o in objs if o.type == "MESH" and (
        any(abs(s - 1) > 1e-4 for s in o.scale) and not (o.data.users > 1))]
    r.check("unapplied_scale", unapplied[:8], not unapplied, "none", "Object > Apply > Scale", severity="warn")
    neg = [o.name for o in objs if o.type == "MESH" and o.scale[0] * o.scale[1] * o.scale[2] < 0]
    r.check("negative_scale", neg[:8], not neg, "none", "apply scale, then flip normals if needed")
    if not allow_orphans:
        orphans = [d.name for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images)
                   for d in coll if d.users == 0]
        r.check("orphan_datablocks", orphans[:8], not orphans, "none", "purge before saving")
    cams = [o for o in objs if o.type == "CAMERA"]
    r.check("scene_camera", sc.camera.name if sc.camera else None, sc.camera is not None, "set", "set scene.camera",
            severity="warn" if not cams else "error")
    r.info["scene"] = {"objects": len(objs), "collections": len(bpy.data.collections), "frame": [sc.frame_start, sc.frame_end]}


# ----------------------------------------------------------------------------- mesh measurements

def mesh_stats(obj, max_faces=400_000, uv_checks=True):
    """Counts and defects of the *evaluated* mesh (modifiers and Geometry Nodes included)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        out = {"name": obj.name, "verts": len(me.vertices), "faces": len(me.polygons)}
        if len(me.polygons) > max_faces:
            out["skipped"] = f"more than {max_faces} faces"
            return out
        bm = bmesh.new()
        bm.from_mesh(me)
        tris = sum(1 for f in bm.faces if len(f.verts) == 3)
        quads = sum(1 for f in bm.faces if len(f.verts) == 4)
        out.update(tris=tris, quads=quads, ngons=len(bm.faces) - tris - quads,
                   triangles=sum(len(f.verts) - 2 for f in bm.faces))
        out["loose_verts"] = sum(1 for v in bm.verts if not v.link_edges)
        out["boundary_edges"] = sum(1 for e in bm.edges if e.is_boundary)
        out["non_manifold_edges"] = sum(1 for e in bm.edges if e.link_faces and not e.is_manifold and not e.is_boundary)
        out["wire_edges"] = sum(1 for e in bm.edges if not e.link_faces)
        out["zero_area_faces"] = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
        dbl = bmesh.ops.find_doubles(bm, verts=bm.verts, dist=1e-5)["targetmap"]
        out["duplicate_verts"] = len(dbl)
        closed = out["boundary_edges"] == 0 and out["non_manifold_edges"] == 0 and out["wire_edges"] == 0 and bm.faces
        out["closed"] = bool(closed)
        out["volume"] = round(bm.calc_volume(signed=True), 6) if closed else None
        out["inverted"] = bool(closed and out["volume"] is not None and out["volume"] < 0)
        out["smooth_faces"] = sum(1 for f in bm.faces if f.smooth)
        if uv_checks:
            lay = bm.loops.layers.uv.active
            out["uv_layers"] = len(me.uv_layers)
            if lay and bm.faces:
                oob = 0
                dens = []
                for f in bm.faces:
                    pts = [l[lay].uv for l in f.loops]
                    if any(not (-1e-4 <= p[0] <= 1 + 1e-4 and -1e-4 <= p[1] <= 1 + 1e-4) for p in pts):
                        oob += 1
                    ua = 0.0
                    for i in range(1, len(pts) - 1):
                        a, b, c = pts[0], pts[i], pts[i + 1]
                        ua += abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) * 0.5
                    fa = f.calc_area()
                    if fa > 1e-10:
                        dens.append(math.sqrt(ua / fa))
                out["uv_out_of_bounds_faces"] = oob
                if dens:
                    mean = sum(dens) / len(dens)
                    var = sum((d - mean) ** 2 for d in dens) / len(dens)
                    out["texel_density_cv"] = round(math.sqrt(var) / mean, 4) if mean > 0 else None
                    out["uv_zero_faces"] = sum(1 for d in dens if d < 1e-6)
        bm.free()
        out["materials"] = len([s for s in obj.material_slots if s.material])
        out["empty_slots"] = len([s for s in obj.material_slots if not s.material])
        return out
    finally:
        ev.to_mesh_clear()


def mesh_gate(r, objs, max_ngons=None, max_tris=None, require_closed=False, require_uv=False,
              max_texel_cv=None, allow_boundary=True, per_object=True):
    """Defect gate over meshes. Limits are opt-in except the ones that are always wrong
    (loose vertices, zero-area faces, duplicate vertices, inverted volumes, non-manifold edges)."""
    rows = [mesh_stats(o, uv_checks=require_uv or max_texel_cv is not None) for o in objs]
    rows = [m for m in rows if "skipped" not in m]
    total = lambda k: sum(m.get(k, 0) or 0 for m in rows)
    r.info["meshes"] = {"objects": len(rows), "verts": total("verts"), "faces": total("faces"),
                        "triangles": total("triangles")}
    for key, hint in (("loose_verts", "delete loose geometry"), ("zero_area_faces", "dissolve degenerate faces"),
                      ("duplicate_verts", "Merge by Distance"), ("non_manifold_edges", "fix edges shared by 3+ faces")):
        r.check(key, total(key), total(key) == 0, 0, hint)
    inv = [m["name"] for m in rows if m.get("inverted")]
    r.check("inverted_volume", inv[:8], not inv, "none", "Mesh > Normals > Recalculate Outside")
    if max_ngons is not None:
        r.le("ngons", total("ngons"), max_ngons, hint="triangulate or re-quad the n-gons")
    if max_tris is not None:
        r.le("triangles", total("triangles"), max_tris, hint="decimate or reduce subdivision")
    if require_closed:
        open_ = [m["name"] for m in rows if not m.get("closed")]
        r.check("closed_meshes", open_[:8], not open_, "all closed", "fill holes")
    elif not allow_boundary:
        r.le("boundary_edges", total("boundary_edges"), 0)
    if require_uv:
        no_uv = [m["name"] for m in rows if not m.get("uv_layers")]
        r.check("has_uv", no_uv[:8], not no_uv, "all", "unwrap")
        oob = total("uv_out_of_bounds_faces")
        r.check("uv_out_of_bounds_faces", oob, oob == 0, 0, "pack UVs into 0-1", severity="warn")
    if max_texel_cv is not None:
        worst = max((m.get("texel_density_cv") or 0 for m in rows), default=0)
        r.le("texel_density_cv", worst, max_texel_cv, hint="rescale islands to even texel density")
    if per_object:
        r.info["objects"] = rows[:40]
    return rows


# ----------------------------------------------------------------------------- camera framing

def framing(scene, cam, objs):
    """Where the objects' bounding boxes land in the camera frame (normalised 0-1, y up)."""
    from bpy_extras.object_utils import world_to_camera_view
    b = bounds(objs)
    if not b:
        return None
    lo, hi = b
    pts = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    ndc = [world_to_camera_view(scene, cam, p) for p in pts]
    xs, ys = [p.x for p in ndc], [p.y for p in ndc]
    behind = any(p.z <= 0 for p in ndc)
    x0, x1, y0, y1 = max(0, min(xs)), min(1, max(xs)), max(0, min(ys)), min(1, max(ys))
    inside = sum(1 for p in ndc if 0 <= p.x <= 1 and 0 <= p.y <= 1 and p.z > 0)
    return {"behind_camera": behind, "corners_inside": inside,
            "bbox": [round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)],
            "fill": round(max(0, x1 - x0) * max(0, y1 - y0), 4),
            "span": [round(max(0, x1 - x0), 4), round(max(0, y1 - y0), 4)],
            "fit": round(max(max(xs) - min(xs), max(ys) - min(ys)), 4),
            "margin": round(min(min(xs), min(ys), 1 - max(xs), 1 - max(ys)), 4)}


def framing_gate(r, scene, objs, min_fit=0.2, max_fit=0.95, min_margin=0.0):
    """`fit` is the share of the frame taken by the subject along its limiting dimension (width or height)."""
    cam = scene.camera
    if not r.check("camera_exists", cam.name if cam else None, cam is not None, "set", "add a camera"):
        return None
    f = framing(scene, cam, objs)
    if f is None:
        r.check("subject_found", 0, False, ">0 objects")
        return None
    r.info["framing"] = f
    r.check("subject_in_front_of_camera", f["behind_camera"], not f["behind_camera"], False, "move the camera back")
    r.ge("subject_inside_frame_margin", f["margin"], min_margin, hint="subject is cropped: widen the lens or move back")
    r.ge("subject_fit_min", f["fit"], min_fit, hint="subject too small in frame: move closer or use a longer lens")
    r.le("subject_fit_max", f["fit"], max_fit, hint="subject too big, leave air around it")
    return f


def occluded_by(origin, target, others):
    """Names of meshes in `others` that sit between `origin` and the centre of `target` (ray test on raw
    geometry in world space; use it to prove a subject is not hidden behind something)."""
    from mathutils.bvhtree import BVHTree
    centre = target.matrix_world @ (sum((Vector(b) for b in target.bound_box), Vector()) / 8)
    direction = centre - origin
    dist = direction.length
    direction.normalize()
    hits = []
    for o in others:
        if o is target or o.type != "MESH":
            continue
        verts = [o.matrix_world @ v.co for v in o.data.vertices]
        tree = BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in o.data.polygons])
        loc = tree.ray_cast(origin, direction, dist)[0]
        if loc is not None:
            hits.append(o.name)
    return hits


def fcurves_of(action):
    """All F-curves of an action, for Blender 4.x (action.fcurves) and 5.x (layers > strips > channelbags)."""
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                out += list(bag.fcurves)
    return out


def lights_in_frame(scene, cam):
    """Names of area lights that the camera can see directly (visible_camera on and a corner inside the frame).
    An emitter in shot is almost never intended: it hides the subject or burns a white rectangle into the image."""
    from bpy_extras.object_utils import world_to_camera_view
    seen = []
    for o in scene.objects:
        if o.type != "LIGHT" or o.data.type != "AREA" or not getattr(o, "visible_camera", True) or o.hide_render:
            continue
        w, h = o.data.size, (o.data.size_y if o.data.shape in {"RECTANGLE", "ELLIPSE"} else o.data.size)
        corners = [o.matrix_world @ Vector((sx * w / 2, sy * h / 2, 0)) for sx in (-1, 1) for sy in (-1, 1)]
        ndc = [world_to_camera_view(scene, cam, c) for c in corners]
        if any(p.z > 0 for p in ndc) and max(p.x for p in ndc) > 0 and min(p.x for p in ndc) < 1 \
                and max(p.y for p in ndc) > 0 and min(p.y for p in ndc) < 1:
            seen.append(o.name)
    return seen


def lights_gate(r, scene):
    cam = scene.camera
    if cam is None:
        return []
    seen = lights_in_frame(scene, cam)
    r.check("area_lights_not_in_shot", seen, not seen, "none",
            "move the light out of frame or turn off Object > Visibility > Camera on it")
    return seen


# ----------------------------------------------------------------------------- images

def load_pixels(path):
    """Image file -> float32 array (h, w, 4), top row first, values as stored (sRGB for 8-bit files)."""
    import numpy as np
    img = bpy.data.images.load(os.path.abspath(path), check_existing=False)
    try:
        w, h = img.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        return buf.reshape(h, w, 4)[::-1].copy()
    finally:
        bpy.data.images.remove(img)


def _luma(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def _downscale(a, longest=256):
    import numpy as np
    h, w = a.shape[:2]
    k = max(1, int(math.ceil(max(h, w) / longest)))
    h2, w2 = h // k * k, w // k * k
    return a[:h2, :w2].reshape(h2 // k, k, w2 // k, k, a.shape[2]).mean(axis=(1, 3)).astype(np.float32)


def palette(a, k=5, iters=12):
    """k-means over a downscaled copy; returns [{hex, share}] largest first, colours as sRGB hex."""
    import numpy as np
    px = _downscale(a, 96)[..., :3].reshape(-1, 3)
    if len(px) < k:
        return []
    order = np.argsort(_luma(px))
    cent = px[order[np.linspace(0, len(px) - 1, k).astype(int)]].copy()
    for _ in range(iters):
        d = ((px[:, None, :] - cent[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for i in range(k):
            m = lab == i
            if m.any():
                cent[i] = px[m].mean(0)
    share = np.bincount(lab, minlength=k) / len(px)
    out = []
    for i in np.argsort(-share):
        if share[i] < 0.005:
            continue
        c = np.clip(cent[i], 0, 1)
        out.append({"hex": "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in c), "share": round(float(share[i]), 3)})
    return out


def sharpness_grid(a, n=4):
    """Variance of a Laplacian per cell of an n x n grid: where the image is in focus."""
    import numpy as np
    g = _luma(_downscale(a, 384))
    lap = np.abs(4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:])
    h, w = lap.shape
    cells = [[float(lap[i * h // n:(i + 1) * h // n, j * w // n:(j + 1) * w // n].var()) for j in range(n)]
             for i in range(n)]
    top = max(max(row) for row in cells) or 1.0
    return [[round(c / top, 3) for c in row] for row in cells]


def image_stats(a, with_palette=True):
    """Exposure, contrast and colour numbers for an (h, w, 4) array (sRGB-encoded)."""
    import numpy as np
    s = _downscale(a, 512)
    L = _luma(s[..., :3])
    mx, mn = s[..., :3].max(-1), s[..., :3].min(-1)
    sat = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0)
    out = {"size": [int(a.shape[1]), int(a.shape[0])], "mean_luma": round(float(L.mean()), 4),
           "p5": round(float(np.percentile(L, 5)), 4), "p95": round(float(np.percentile(L, 95)), 4),
           "clip_black": round(float((L < 0.01).mean()), 4), "clip_white": round(float((L > 0.99).mean()), 4),
           "mean_saturation": round(float(sat.mean()), 4),
           "mean_rgb": [round(float(v), 4) for v in s[..., :3].reshape(-1, 3).mean(0)]}
    out["contrast"] = round(out["p95"] - out["p5"], 4)
    out["transparent"] = round(float((s[..., 3] < 0.99).mean()), 4)
    if with_palette:
        out["palette"] = palette(a)
    return out


def _to_linear_arr(a):
    import numpy as np
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def compare(a, b):
    """How far image a is from reference b (both (h, w, 4)); sizes are matched by downscaling."""
    import numpy as np
    n = min(a.shape[0], b.shape[0], 256), min(a.shape[1], b.shape[1], 256)

    def fit(x):
        y = _downscale(x, 256)
        return y[:n[0], :n[1], :3]

    A, B = fit(a), fit(b)
    la, lb = _luma(A), _luma(B)
    cc = float(np.corrcoef(la.ravel(), lb.ravel())[0, 1]) if la.std() > 1e-6 and lb.std() > 1e-6 else 0.0
    lin_a, lin_b = float(_luma(_to_linear_arr(A)).mean()), float(_luma(_to_linear_arr(B)).mean())
    stops = math.log2(max(lin_a, 1e-6) / max(lin_b, 1e-6))
    return {"mean_abs_error": round(float(np.abs(A - B).mean()), 4),
            "exposure_stops": round(stops, 3),
            "luma_shift": round(float(la.mean() - lb.mean()), 4),
            "rgb_shift": [round(float(v), 4) for v in (A - B).reshape(-1, 3).mean(0)],
            "contrast_ratio": round(float((np.percentile(la, 95) - np.percentile(la, 5)) /
                                          max(1e-4, np.percentile(lb, 95) - np.percentile(lb, 5))), 3),
            "luma_correlation": round(cc, 4)}


def to_srgb(v):
    """One linear value -> sRGB-encoded value (0-1)."""
    v = min(1.0, max(0.0, v))
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def to_linear(v):
    """One sRGB-encoded value -> linear."""
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def hex_to_linear(h):
    """'#rrggbb' (sRGB) -> linear RGB tuple for shader inputs."""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(to_linear(v) for v in c)


def linear_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(round(to_srgb(v) * 255)) for v in rgb[:3])


# ----------------------------------------------------------------------------- rendering

def render(path, samples=None, percent=None, engine=None, scene=None, denoise=True, still=True):
    """Render the scene camera to `path`, then restore every setting touched. Returns the path."""
    sc = scene or bpy.context.scene
    keep = {"engine": sc.render.engine, "pct": sc.render.resolution_percentage, "path": sc.render.filepath,
            "fmt": sc.render.image_settings.file_format}
    cyc = getattr(sc, "cycles", None)
    if cyc:
        keep.update(samples=cyc.samples, denoise=cyc.use_denoising)
    try:
        if engine:
            sc.render.engine = engine
        if percent:
            sc.render.resolution_percentage = percent
        if cyc and sc.render.engine == "CYCLES":
            if samples:
                cyc.samples = samples
            cyc.use_denoising = denoise
        sc.render.image_settings.file_format = "PNG"
        sc.render.filepath = os.path.abspath(path)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        bpy.ops.render.render(write_still=still, scene=sc.name)
    finally:
        sc.render.engine, sc.render.resolution_percentage = keep["engine"], keep["pct"]
        sc.render.filepath, sc.render.image_settings.file_format = keep["path"], keep["fmt"]
        if cyc and "samples" in keep:
            cyc.samples, cyc.use_denoising = keep["samples"], keep["denoise"]
    return os.path.abspath(path)


def exposure_gate(r, path, max_clip_white=0.02, max_clip_black=0.10, min_contrast=0.25, mean_luma=(0.12, 0.75)):
    """Render sanity: not blown out, not crushed, has contrast, sensible brightness."""
    a = load_pixels(path)
    st = image_stats(a)
    r.info["image"] = st
    r.le("clipped_white", st["clip_white"], max_clip_white, hint="lower light energy or use a softer view transform look")
    r.le("clipped_black", st["clip_black"], max_clip_black, hint="add fill or raise world strength")
    r.ge("contrast_p95_p5", st["contrast"], min_contrast, hint="flat image: add a key/fill ratio or a darker background")
    r.check("mean_luma", st["mean_luma"], mean_luma[0] <= st["mean_luma"] <= mean_luma[1], f"{mean_luma[0]}..{mean_luma[1]}",
            "too dark or too bright overall")
    return st


# ----------------------------------------------------------------------------- node trees

def _scratch_defaults(tree):
    """A throwaway tree of the same type, used to know which values differ from a fresh node."""
    return bpy.data.node_groups.new("_gauge_scratch", tree.bl_idname)


def _val(v):
    if hasattr(v, "__len__") and not isinstance(v, str):
        return [round(float(x), 4) for x in v]
    if isinstance(v, float):
        return round(v, 4)
    if hasattr(v, "name"):
        return v.name
    return v


def _socket_value(s):
    if not hasattr(s, "default_value"):
        return None
    try:
        return _val(s.default_value)
    except Exception:
        return None


def node_dump(tree, include_defaults=False):
    """JSON-able description of a node tree: nodes (type, settings, changed inputs) and links."""
    scratch = None if include_defaults else _scratch_defaults(tree)
    nodes, links = {}, []
    names = {}
    for n in tree.nodes:
        key = re.sub(r"[.\s]+", "_", n.name)
        names[n.name] = key
    try:
        for n in tree.nodes:
            ref = None
            if scratch is not None:
                try:
                    ref = scratch.nodes.new(n.bl_idname)
                except Exception:
                    ref = None
            entry = {"type": n.bl_idname}
            sets = {}
            for p in n.bl_rna.properties:
                if p.is_readonly or p.identifier in {"name", "label", "location", "width", "height", "dimensions", "parent",
                                                     "select", "show_options", "show_preview", "show_texture", "hide",
                                                     "mute", "use_custom_color", "color", "inputs", "outputs", "internal_links",
                                                     "node_tree", "bl_idname", "bl_label", "bl_description", "bl_icon",
                                                     "bl_static_type", "bl_width_default", "bl_width_min", "bl_width_max",
                                                     "bl_height_default", "bl_height_min", "bl_height_max", "image_user",
                                                     "interface", "color_ramp", "mapping", "cursor_location"}:
                    continue
                if p.type in {"POINTER", "COLLECTION"}:
                    ptr = getattr(n, p.identifier, None) if p.type == "POINTER" else None
                    if isinstance(ptr, bpy.types.ID):
                        sets[p.identifier] = ptr.name
                    continue
                v = getattr(n, p.identifier)
                if ref is not None and getattr(ref, p.identifier, None) == v:
                    continue
                sets[p.identifier] = _val(v) if p.type != "ENUM" else v
            if n.bl_idname == "ShaderNodeValToRGB":
                sets["color_ramp"] = {"interpolation": n.color_ramp.interpolation,
                                      "stops": [[round(e.position, 4), _val(e.color)] for e in n.color_ramp.elements]}
            if n.bl_idname == "ShaderNodeGroup" and n.node_tree:
                sets["node_tree"] = n.node_tree.name
            ins = {}
            for i, s in enumerate(n.inputs):
                if s.is_linked or not hasattr(s, "default_value") or not s.enabled:
                    continue
                v = _socket_value(s)
                rv = _socket_value(ref.inputs[i]) if ref is not None and i < len(ref.inputs) else None
                if include_defaults or v != rv:
                    ins[s.name if sum(1 for t in n.inputs if t.name == s.name) == 1 else s.identifier] = v
            if sets:
                entry["set"] = sets
            if ins:
                entry["in"] = ins
            if n.label:
                entry["label"] = n.label
            if n.mute:
                entry["mute"] = True
            entry["at"] = [round(n.location.x), round(n.location.y)]
            nodes[names[n.name]] = entry
        for l in tree.links:
            if not l.is_valid:
                continue
            fo = l.from_socket
            ti = l.to_socket
            fname = fo.name if sum(1 for t in l.from_node.outputs if t.name == fo.name) == 1 else fo.identifier
            tname = ti.name if sum(1 for t in l.to_node.inputs if t.name == ti.name) == 1 else ti.identifier
            links.append([f"{names[l.from_node.name]}.{fname}", f"{names[l.to_node.name]}.{tname}"])
    finally:
        if scratch is not None:
            bpy.data.node_groups.remove(scratch)
    return {"nodes": nodes, "links": links}


_ID_BY_KIND = {"MATERIAL": "materials", "OBJECT": "objects", "COLLECTION": "collections", "IMAGE": "images",
               "TEXTURE": "textures", "WORLD": "worlds"}


def _find_socket(sockets, name):
    for s in sockets:
        if s.name == name and s.enabled:
            return s
    for s in sockets:
        if s.identifier == name:
            return s
    for s in sockets:
        if s.name == name:
            return s
    raise KeyError(f"no socket '{name}' (have: {[s.name for s in sockets]})")


def _assign(sock, value):
    if value is None:
        return
    kind = getattr(sock, "type", "")
    if kind in _ID_BY_KIND and isinstance(value, str):
        coll = getattr(bpy.data, _ID_BY_KIND[kind])
        if value not in coll:
            raise KeyError(f"{kind.lower()} '{value}' does not exist")
        sock.default_value = coll[value]
    elif isinstance(value, str) and value.startswith("#") and hasattr(sock.default_value, "__len__"):
        rgb = hex_to_linear(value)
        sock.default_value = rgb + (1.0,) if len(sock.default_value) == 4 else rgb
    elif isinstance(value, (list, tuple)) and hasattr(sock.default_value, "__len__"):
        n = len(sock.default_value)
        v = list(value) + [1.0] * (n - len(value))
        sock.default_value = v[:n]
    else:
        sock.default_value = value


def node_build(tree, spec, clear=True):
    """Build `spec` ({'nodes': {key: {type, set, in, at}}, 'links': [['a.Out', 'b.In']]}) into `tree`.
    Raises with the node key and socket name on any mistake, so a bad spec never half-builds silently."""
    if clear:
        tree.nodes.clear()
    made = {}
    for i, (key, d) in enumerate(spec["nodes"].items()):
        n = tree.nodes.new(d["type"])
        n.name = key
        if d.get("label"):
            n.label = d["label"]
        n.location = d.get("at", (i * 220, 0))
        made[key] = n
    for key, d in spec["nodes"].items():
        n = made[key]
        try:
            for attr, v in (d.get("set") or {}).items():
                if attr == "color_ramp":
                    cr = n.color_ramp
                    cr.interpolation = v.get("interpolation", cr.interpolation)
                    while len(cr.elements) > len(v["stops"]):
                        cr.elements.remove(cr.elements[-1])
                    while len(cr.elements) < len(v["stops"]):
                        cr.elements.new(0.5)
                    for e, (pos, col) in zip(cr.elements, v["stops"]):
                        e.position, e.color = pos, (col if len(col) == 4 else list(col) + [1.0])
                elif attr == "node_tree":
                    n.node_tree = bpy.data.node_groups[v]
                elif attr == "image" and isinstance(v, str):
                    n.image = bpy.data.images[v]
                else:
                    setattr(n, attr, v)
            for sname, v in (d.get("in") or {}).items():
                _assign(_find_socket(n.inputs, sname), v)
            if d.get("mute"):
                n.mute = True
        except Exception as e:
            raise RuntimeError(f"node '{key}' ({d['type']}): {e}") from None
    for a, b in spec.get("links", []):
        ka, sa = a.split(".", 1)
        kb, sb = b.split(".", 1)
        try:
            tree.links.new(_find_socket(made[ka].outputs, sa), _find_socket(made[kb].inputs, sb))
        except Exception as e:
            raise RuntimeError(f"link {a} -> {b}: {e}") from None
    return made


def node_text(tree, max_lines=200):
    """Readable text of a node tree in data-flow order, for reading a tree you did not build."""
    d = node_dump(tree)
    order, seen = [], set()
    incoming = {}
    for a, b in d["links"]:
        incoming.setdefault(b.split(".", 1)[0], set()).add(a.split(".", 1)[0])

    def visit(k):
        if k in seen:
            return
        seen.add(k)
        for p in sorted(incoming.get(k, ())):
            visit(p)
        order.append(k)

    for k in d["nodes"]:
        visit(k)
    lines = []
    for k in order:
        e = d["nodes"][k]
        bits = [f"{k} [{e['type'].replace('ShaderNode', '').replace('GeometryNode', '').replace('CompositorNode', '')}]"]
        if e.get("set"):
            bits.append(" ".join(f"{a}={v}" for a, v in e["set"].items() if a != "color_ramp"))
        if e.get("in"):
            bits.append("in: " + ", ".join(f"{a}={v}" for a, v in e["in"].items()))
        lines.append(" ".join(bits))
        for a, b in d["links"]:
            if b.split(".", 1)[0] == k:
                lines.append(f"    <- {a}  ->  .{b.split('.', 1)[1]}")
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... {len(lines) - max_lines} more lines"]
    return "\n".join(lines)


_COLOR_DATA_SLOTS = {"Roughness", "Metallic", "Normal", "Height", "Displacement", "Alpha", "IOR", "Specular IOR Level",
                     "Transmission Weight", "Coat Weight", "Sheen Weight", "Emission Strength", "Strength"}


def node_gate(r, tree, label=None):
    """Structural health of one node tree."""
    tag = label or tree.name
    nodes = list(tree.nodes)
    out_types = {"ShaderNodeOutputMaterial", "NodeGroupOutput", "ShaderNodeOutputWorld", "ShaderNodeOutputLight",
                 "CompositorNodeComposite", "NodeGroupInput", "NodeFrame", "NodeReroute", "CompositorNodeViewer"}
    bad_links = [f"{l.from_node.name}->{l.to_node.name}" for l in tree.links if not l.is_valid]
    r.check(f"{tag}: valid_links", bad_links[:6], not bad_links, "none", "relink: sockets types or node removal broke these")
    dead = [n.name for n in nodes if n.bl_idname not in out_types and not any(s.is_linked for s in n.outputs)
            and n.bl_idname not in {"ShaderNodeValue", "ShaderNodeRGB"} and not n.mute]
    r.check(f"{tag}: unused_nodes", dead[:8], not dead, "none", "delete nodes whose output goes nowhere", severity="warn")
    muted = [n.name for n in nodes if n.mute]
    r.check(f"{tag}: muted_nodes", muted[:8], not muted, "none", "muted nodes are usually leftovers", severity="warn")
    if tree.bl_idname == "ShaderNodeTree":
        outs = [n for n in nodes if n.bl_idname in {"ShaderNodeOutputMaterial", "ShaderNodeOutputWorld", "ShaderNodeOutputLight"}]
        has = any(any(s.is_linked for s in o.inputs) for o in outs) if outs else True
        r.check(f"{tag}: output_connected", has, has, True, "connect a shader to the output node")
        miss = [n.name for n in nodes if n.bl_idname == "ShaderNodeTexImage" and n.image is None]
        r.check(f"{tag}: image_nodes_have_image", miss[:6], not miss, "none", "assign an image or remove the node")
        wrong = []
        for l in tree.links:
            if l.from_node.bl_idname == "ShaderNodeTexImage" and l.from_node.image and l.to_socket.name in _COLOR_DATA_SLOTS:
                if l.from_node.image.colorspace_settings.name not in ("Non-Color", "Raw", "Linear Rec.709", "Linear"):
                    wrong.append(l.from_node.image.name)
        r.check(f"{tag}: data_textures_non_color", wrong[:6], not wrong, "Non-Color",
                "set the image Color Space to Non-Color (roughness, metal, normal, height)")
    if tree.bl_idname == "GeometryNodeTree":
        gout = [n for n in nodes if n.bl_idname == "NodeGroupOutput"]
        ok = bool(gout) and any(s.is_linked for s in gout[0].inputs)
        r.check(f"{tag}: group_output_connected", ok, ok, True, "connect a geometry to Group Output")
    r.info.setdefault("trees", {})[tag] = {"nodes": len(nodes), "links": len(tree.links)}


_SOCKET_TYPES = {"Geometry": "NodeSocketGeometry", "Float": "NodeSocketFloat", "Int": "NodeSocketInt",
                 "Bool": "NodeSocketBool", "Vector": "NodeSocketVector", "Object": "NodeSocketObject",
                 "Material": "NodeSocketMaterial", "Collection": "NodeSocketCollection", "Color": "NodeSocketColor",
                 "Rotation": "NodeSocketRotation", "String": "NodeSocketString"}


def gn_make(name, spec):
    """Create (or rebuild) the Geometry Nodes group `name` from a spec:

        {"interface": {"inputs": [{"name": "Width", "type": "Float", "default": 4.0, "min": 0.1, "max": 50}],
                       "outputs": [{"name": "Geometry", "type": "Geometry"}]},
         "nodes": {...}, "links": [["gin.Width", "grid.Size X"], ...]}     # same node/link format as node_build

    Group Input / Output nodes are 'NodeGroupInput' / 'NodeGroupOutput'. Rebuilding recreates the interface, so
    set modifier values again afterwards with gn_set. Returns the group."""
    g = bpy.data.node_groups.get(name)
    if g is None:
        g = bpy.data.node_groups.new(name, "GeometryNodeTree")
    else:
        g.interface.clear()
        g.nodes.clear()
    iface = spec.get("interface") or {"inputs": [{"name": "Geometry", "type": "Geometry"}],
                                      "outputs": [{"name": "Geometry", "type": "Geometry"}]}
    for io, key in (("OUTPUT", "outputs"), ("INPUT", "inputs")):
        for item in iface.get(key, []):
            sock = g.interface.new_socket(item["name"], in_out=io, socket_type=_SOCKET_TYPES[item["type"]])
            if "default" in item:
                sock.default_value = item["default"]
            if "min" in item:
                sock.min_value = item["min"]
            if "max" in item:
                sock.max_value = item["max"]
    node_build(g, spec)
    return g


def instance_positions(obj):
    """World positions of the instances an object produces (Geometry Nodes instancing)."""
    dg = bpy.context.evaluated_depsgraph_get()
    return [tuple(i.matrix_world.translation) for i in dg.object_instances
            if i.is_instance and i.parent and i.parent.original == obj]


def grid_step(positions, tol=1e-4):
    """For instances laid out on a regular XY grid: the largest height (Z) jump between neighbouring cells
    and the average, in metres. A smooth landscape has small steps; salt-and-pepper noise has large ones."""
    xs = sorted({round(p[0] / tol) for p in positions})
    ys = sorted({round(p[1] / tol) for p in positions})
    ix = {v: i for i, v in enumerate(xs)}
    iy = {v: i for i, v in enumerate(ys)}
    z = {(ix[round(p[0] / tol)], iy[round(p[1] / tol)]): p[2] for p in positions}
    steps = []
    for (i, j), v in z.items():
        for nb in ((i + 1, j), (i, j + 1)):
            if nb in z:
                steps.append(abs(z[nb] - v))
    return {"cells": len(z), "grid": [len(xs), len(ys)], "max_step": max(steps, default=0.0),
            "mean_step": sum(steps) / len(steps) if steps else 0.0}


def gn_inputs(group):
    """{input name: socket identifier} of a Geometry Nodes group's interface."""
    return {i.name: i.identifier for i in group.interface.items_tree
            if i.item_type == "SOCKET" and i.in_out == "INPUT"}


def gn_set(mod, **values):
    """Set Geometry Nodes modifier inputs by their interface *name*. Blender 5.x no longer allows
    mod["Socket_1"] = v; the value lives in mod.properties.inputs[identifier]["value"]."""
    ids = gn_inputs(mod.node_group)
    for name, v in values.items():
        if name not in ids:
            raise KeyError(f"group '{mod.node_group.name}' has no input '{name}' (have: {sorted(ids)})")
        kind = next((i.socket_type for i in mod.node_group.interface.items_tree
                     if i.item_type == "SOCKET" and i.in_out == "INPUT" and i.name == name), "")
        if isinstance(v, str):
            for coll in ("objects", "materials", "collections", "images"):
                if v in getattr(bpy.data, coll):
                    v = getattr(bpy.data, coll)[v]
                    break
        elif kind == "NodeSocketFloat":
            v = float(v)  # an int written to a float input is silently ignored by Blender
        elif kind == "NodeSocketInt":
            v = int(round(v))
        elif kind == "NodeSocketBool":
            v = bool(v)
        elif kind == "NodeSocketVector" and not isinstance(v, (int, float)):
            v = tuple(float(x) for x in v)
        ins = mod.properties.inputs
        if ids[name] in ins:
            ins[ids[name]]["value"] = v
        else:
            ins[ids[name]] = {"value": v}  # first write creates the entry; later writes use ["value"]
    mod.id_data.update_tag()


def gn_get(mod, name):
    ident = gn_inputs(mod.node_group)[name]
    ins = mod.properties.inputs
    if ident in ins:
        v = ins[ident]["value"]
        return list(v) if hasattr(v, "__len__") and not isinstance(v, str) else v
    for i in mod.node_group.interface.items_tree:
        if getattr(i, "identifier", None) == ident:
            d = i.default_value
            return list(d) if hasattr(d, "__len__") and not isinstance(d, str) else d


def instance_count(obj):
    """How many instances the evaluated object carries (Geometry Nodes instancing), 0 if none."""
    dg = bpy.context.evaluated_depsgraph_get()
    return sum(1 for inst in dg.object_instances if inst.is_instance and inst.parent and inst.parent.original == obj)


def state_save(scene=None, key="gauge_prev"):
    """Remember camera, world, engine and colour settings in a scene property so work can be undone later."""
    sc = scene or bpy.context.scene
    st = {"camera": sc.camera.name if sc.camera else None, "world": sc.world.name if sc.world else None,
          "engine": sc.render.engine, "res": [sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage],
          "view": sc.view_settings.view_transform, "look": sc.view_settings.look, "frame": [sc.frame_start, sc.frame_end]}
    if hasattr(sc, "cycles"):
        st["samples"] = sc.cycles.samples
    sc[key] = json.dumps(st)
    return st


def state_restore(scene=None, key="gauge_prev"):
    """Put back what state_save remembered. Returns what was restored (empty dict when nothing was saved)."""
    sc = scene or bpy.context.scene
    if key not in sc:
        return {}
    st = json.loads(sc[key])
    sc.camera = bpy.data.objects.get(st["camera"]) if st["camera"] else None
    sc.world = bpy.data.worlds.get(st["world"]) if st["world"] else None
    for attr, val in (("engine", st["engine"]),):
        try:
            setattr(sc.render, attr, val)
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = st["res"]
    for obj, attr, val in ((sc.view_settings, "view_transform", st["view"]), (sc.view_settings, "look", st["look"])):
        try:
            setattr(obj, attr, val)
        except TypeError:
            pass
    sc.frame_start, sc.frame_end = st["frame"]
    if "samples" in st and hasattr(sc, "cycles"):
        sc.cycles.samples = st["samples"]
    del sc[key]
    return st


# ----------------------------------------------------------------------------- isolated workspace

def workspace_make(name, scene=None):
    """Collection `name` made active; returns the collection (created or emptied of nothing)."""
    sc = scene or bpy.context.scene
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    lc = bpy.context.view_layer.layer_collection.children.get(name)
    if lc:
        bpy.context.view_layer.active_layer_collection = lc
    return col


def workspace_remove(name, confirm=False):
    """Delete a collection and its objects. Without confirm=True it only reports what it would delete."""
    col = bpy.data.collections.get(name)
    if not col:
        return {"collection": name, "found": False}
    objs = sorted(o.name for o in col.all_objects)
    result = {"collection": name, "found": True, "objects": objs, "deleted": False}
    if confirm:
        for o in list(col.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for c in list(col.children_recursive):
            bpy.data.collections.remove(c)
        bpy.data.collections.remove(col)
        result["deleted"] = True
    return result


def clear_scene():
    """Empty bpy.data of scene content (used by headless fixtures, never by live-session scripts)."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights,
                 bpy.data.curves, bpy.data.node_groups, bpy.data.collections):
        for d in list(coll):
            coll.remove(d)
