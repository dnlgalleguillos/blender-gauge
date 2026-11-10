---
name: gauge-modeling
description: Model hard-surface and prop meshes in Blender with bmesh and verify them with numbers - n-gons, holes, flipped normals, duplicate and loose geometry, UV density. Ships a bevelled parts kit, a gate and a safe repair script. Use when building or reviewing any mesh.
---

# Gauge modeling

Build with `bmesh`/data API (works with no UI context), then **gate the evaluated mesh** so modifiers and Geometry Nodes are counted.

## Build
`scripts/kit.py` (import it from a script next to it):

| Function | Makes |
|---|---|
| `rounded_box(name, size, bevel, segments, loc, rot, collection)` | box with real bevels in the mesh, smooth by angle |
| `cylinder(name, radius, depth, segments, bevel, ...)` | cylinder with bevelled caps |
| `bolt_head(name, radius, height, sides, bevel, ...)` | hex (or round) bolt head |
| `cut_holes(target, [(u, v, r), ...])` | round holes through the thinnest axis (boolean, then baked) |
| `bake_modifiers(ob)` | applies the whole stack without `bpy.ops` |
| `assign(ob, material)` | single material slot |

Builders replace an object of the same name, so scripts can be re-run. `scripts/build_prop.py` builds a whole prop from a JSON parts list (or the demo crate) into its own collection and gates it:

```
run_blender_script path=skills/gauge-modeling/scripts/build_prop.py args={"name": "crate", "spec": "parts.json"}
```

## Gate
`scripts/mesh_gate.py` -> gate `mesh-health`.

| Check | Fails when | Typical fix |
|---|---|---|
| `loose_verts`, `zero_area_faces`, `duplicate_verts` | any | `fix_mesh.py` |
| `non_manifold_edges` | edge shared by 3+ faces | rebuild that area |
| `inverted_volume` | closed mesh with negative volume | `fix_mesh.py` (`normals`) |
| `ngons` | more than `max_ngons` (opt-in) | `fix_mesh.py` with `triangulate_ngons`, or re-quad |
| `triangles` | more than `max_tris` (opt-in) | decimate, fewer bevel segments |
| `closed_meshes` | `require_closed` and a hole exists | fill |
| `has_uv`, `texel_density_cv` | `require_uv` / limit given | unwrap, even out island scale |

`fix_mesh.py` is a dry run until `apply=true`; it never touches shared mesh data used outside the selection.

## Rules
- Real-world size first (metres), then bevel: a bevel is a fraction of the *smallest* dimension (1-4 %). Hard edges with no bevel catch no light.
- Bevel before smoothing; smooth by angle (35 deg) instead of per-face flags.
- Booleans leave n-gons on cut faces: fine for stills, triangulate before export to engines.
- Keep parts as separate named objects until the end; join only for export.
- After any change: gate, then `look` from `angles` in clay shading to judge form.
