"""Fixtures shared by the in-Blender skill tests."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "lib"))

import bmesh
import bpy

import gauge
from suite import run, run_script, test


def skill_script(skill, name):
    return os.path.join(ROOT, "skills", skill, "scripts", name)


def fresh():
    gauge.clear_scene()
    sc = bpy.context.scene
    sc.camera = None
    sc.unit_settings.system, sc.unit_settings.scale_length = "METRIC", 1.0
    return sc


def mesh_obj(name, verts, faces, loc=(0, 0, 0), collection=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def cube(name="Box", size=2.0, loc=(0, 0, 0), collection=None):
    h = size / 2
    v = [(x, y, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = mesh_obj(name, v, f, loc, collection)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def camera_at(loc=(0, -8, 0), rot=(1.5708, 0, 0), lens=50):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    cam = bpy.data.objects.new("Cam", cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location, cam.rotation_euler = loc, rot
    bpy.context.scene.camera = cam
    bpy.context.view_layer.update()
    return cam


def failed(gate):
    return {c["name"] for c in gate["failed_checks"]} if "failed_checks" in gate else set(gate["failed"])
