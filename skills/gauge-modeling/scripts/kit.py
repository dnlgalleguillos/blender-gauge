"""Hard-surface parts built with bmesh only (no bpy.ops), so they work in any context.

Usage (import it from a script that sits next to it):
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kit
    crate = kit.rounded_box("crate", (1, 0.6, 0.5), bevel=0.02, loc=(0, 0, 0.25))

Every builder returns the new object, links it to `collection` (default: the active collection of the scene),
and uses real-world metres. Bevels are applied to the mesh (not left as modifiers) so the result measures
the same everywhere. `bake_modifiers` does the same for any modifier stack, without operators.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector


def _link(ob, collection):
    col = collection if collection is not None else bpy.context.view_layer.active_layer_collection.collection
    if isinstance(col, str):
        col = bpy.data.collections.get(col) or bpy.data.collections.new(col)
        if col.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(col)
    col.objects.link(ob)
    return ob


def _finish(name, bm, loc, rot, collection, smooth_angle):
    if smooth_angle is not None:
        smooth_by_angle(bm, smooth_angle)
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    old = bpy.data.objects.get(name)
    if old:  # idempotent: rebuilding replaces
        bpy.data.objects.remove(old, do_unlink=True)
    ob = bpy.data.objects.new(name, me)
    ob.location, ob.rotation_euler = loc, rot
    return _link(ob, collection)


def smooth_by_angle(bm, degrees=35.0):
    """Smooth shading with sharp edges where faces meet at more than `degrees` (replaces auto smooth)."""
    lim = math.radians(degrees)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) <= lim
        else:
            e.smooth = True


def rounded_box(name, size=(1, 1, 1), bevel=0.02, segments=3, loc=(0, 0, 0), rot=(0, 0, 0), collection=None,
                smooth_angle=35.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if bevel > 0:
        w = min(bevel, min(size) * 0.49)
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=w, segments=segments, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return _finish(name, bm, loc, rot, collection, smooth_angle)


def cylinder(name, radius=0.1, depth=0.2, segments=32, bevel=0.0, bevel_segments=2, loc=(0, 0, 0),
             rot=(0, 0, 0), collection=None, smooth_angle=35.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=radius, radius2=radius,
                          depth=depth, matrix=Matrix.Identity(4))
    if bevel > 0:
        cap_edges = [e for e in bm.edges if all(abs(abs(v.co.z) - depth / 2) < 1e-6 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=cap_edges, offset=min(bevel, radius * 0.45, depth * 0.45), segments=bevel_segments,
                        profile=0.5, affect="EDGES")
    return _finish(name, bm, loc, rot, collection, smooth_angle)


def bolt_head(name, radius=0.012, height=0.008, sides=6, bevel=0.0015, loc=(0, 0, 0), rot=(0, 0, 0), collection=None):
    """Hex (or round, sides>=16) bolt head with a chamfered top."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=sides, radius1=radius, radius2=radius,
                          depth=height, matrix=Matrix.Translation((0, 0, height / 2)))
    top = [e for e in bm.edges if all(abs(v.co.z - height) < 1e-6 for v in e.verts)]
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=top, offset=bevel, segments=2, profile=0.5, affect="EDGES")
    return _finish(name, bm, loc, rot, collection, 30.0)


def bake_modifiers(ob):
    """Apply the whole modifier stack to the mesh without bpy.ops. Returns the object."""
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = new
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def cut_holes(target, holes, depth=None, segments=32, solver="EXACT"):
    """Boolean-subtract round holes [(u, v, radius), ...] straight through the thinnest axis of `target`
    (u, v = target-local coordinates in the other two axes, in X, Y, Z order). The result is baked into the
    mesh. Returns the target."""
    dims = tuple(target.dimensions)
    axis = dims.index(min(dims))
    d = depth or (dims[axis] * 1.2 + 0.01)
    rot = {2: (0, 0, 0), 1: (math.pi / 2, 0, 0), 0: (0, math.pi / 2, 0)}[axis]
    place = {2: lambda u, v: (u, v, 0), 1: lambda u, v: (u, 0, v), 0: lambda u, v: (0, u, v)}[axis]
    cutters = []
    for i, (u, v, rad) in enumerate(holes):
        c = cylinder(f"{target.name}_cutter{i}", rad, d, segments, rot=rot, smooth_angle=None,
                     collection=target.users_collection[0])
        c.parent = target
        c.location = place(u, v)
        c.hide_render = True
        cutters.append(c)
    bpy.context.view_layer.update()
    for c in cutters:
        m = target.modifiers.new("cut", "BOOLEAN")
        m.operation, m.object, m.solver = "DIFFERENCE", c, solver
    bake_modifiers(target)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)
    return target


def assign(ob, material):
    """Set the object's single material slot (material = datablock or name)."""
    mat = bpy.data.materials[material] if isinstance(material, str) else material
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return ob
