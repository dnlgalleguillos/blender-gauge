"""Tidy a scene safely. Dry run unless apply=true.

Usage (live):  run_blender_script path=skills/gauge-scene/scripts/tidy.py args={"steps": ["units","scale"], "apply": true}
Usage (file):  python run_headless.py tidy.py --blend scene.blend apply=true steps='["units","scale","organize"]'
Args: steps (list, default ["units","scale","organize"]; also "purge"), apply (bool, false).
Prints one GAUGE_JSON line, gate "tidy", with info.actions = what was (or would be) done and info.skipped.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Matrix

import gauge

P = gauge.params(globals(), steps=["units", "scale", "organize"], apply=False)
sc = bpy.context.scene
actions, skipped = [], []


def act(text, fn=None):
    actions.append(text)
    if P["apply"] and fn:
        fn()


if "units" in P["steps"]:
    us = sc.unit_settings
    if us.system != "METRIC" or abs(us.scale_length - 1.0) > 1e-6 or us.length_unit != "METERS":
        def fix_units():
            us.system, us.scale_length, us.length_unit = "METRIC", 1.0, "METERS"
        act(f"units: {us.system}/{us.scale_length:g} -> METRIC/1 (metres)", fix_units)

if "scale" in P["steps"]:
    for o in sc.objects:
        if o.type != "MESH" or all(abs(s - 1) < 1e-6 for s in o.scale):
            continue
        if o.data.users > 1:
            skipped.append(f"{o.name}: shares mesh data")
        elif o.children:
            skipped.append(f"{o.name}: has children (applying would move them)")
        elif o.scale[0] * o.scale[1] * o.scale[2] < 0:
            skipped.append(f"{o.name}: negative scale (flip normals after applying by hand)")
        else:
            def bake(o=o):
                o.data.transform(Matrix.Diagonal((*o.scale, 1.0)))
                o.scale = (1, 1, 1)
                o.data.update()
            act(f"scale: bake {tuple(round(s, 4) for s in o.scale)} into {o.name}", bake)

if "organize" in P["steps"]:
    names = {"MESH": "Meshes", "LIGHT": "Lights", "CAMERA": "Cameras"}
    for o in list(sc.collection.objects):
        target = names.get(o.type, "Other")

        def move(o=o, target=target):
            col = bpy.data.collections.get(target) or bpy.data.collections.new(target)
            if col.name not in sc.collection.children:
                sc.collection.children.link(col)
            col.objects.link(o)
            sc.collection.objects.unlink(o)
        act(f"organize: {o.name} -> {target}", move)

if "purge" in P["steps"]:
    orphans = [(c, d) for c in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights)
               for d in c if d.users == 0]
    for c, d in orphans:
        act(f"purge: {d.name}", lambda c=c, d=d: c.remove(d))

if P["apply"]:
    bpy.context.view_layer.update()
r = gauge.Report("tidy")
r.check("applied" if P["apply"] else "dry_run", len(actions), True)
r.info.update(actions=actions[:60], skipped=skipped[:30], applied=bool(P["apply"]))
r.emit()
