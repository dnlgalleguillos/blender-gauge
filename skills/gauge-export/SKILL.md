---
name: gauge-export
description: Export Blender objects to glTF/GLB, FBX, OBJ, STL, USD or PLY and verify the file by importing it back into a scratch scene - triangle count, size, materials, budgets for web, mobile or desktop. Use before handing an asset to a game engine, web viewer or another tool.
---

# Gauge export

An export is only done when the **file** has been read back and matches the scene.

```
run_blender_script path=skills/gauge-export/scripts/export.py
  args={"out":"/tmp/crate.glb","objects":"Props","budget":"web"}
```
The extension picks the format: `.glb` `.gltf` `.fbx` `.obj` `.stl` `.usd/.usda/.usdc` `.ply`.

## What the gate checks (`export`)
| Check | Meaning |
|---|---|
| `triangles_budget` | scene triangles <= budget (web 100k, mobile 30k, desktop 500k, or `max_tris`) |
| `texture_size_budget` | no texture larger than `max_texture_px` (web 2048, mobile 1024, desktop 4096) |
| `object_count_budget` | optional `max_objects` (draw calls) |
| `file_written` | the file exists and is not empty |
| `roundtrip_triangles` | import it again: same number of triangles |
| `roundtrip_size_error` | same bounding-box dimensions (compared sorted, axes differ between formats) within `tolerance` |
| `roundtrip_materials` | materials survive in formats that carry them |
| `import_cleaned_up` | the scratch import left nothing behind in the session |

## Before exporting
1. `gauge-scene` gate: metric, scale applied, named collections.
2. `gauge-modeling` gate with `max_tris` for the target, triangulate n-gons for engines.
3. `gauge-materials` gate: data textures in Non-Color.

## Format notes
- glTF/GLB: Y-up on disk, PBR materials map directly; written without mesh compression (no extra libraries needed). Best default for web and Godot.
- FBX: for Unity/Unreal pipelines; unit and axis handling differ per engine, check the round-trip size.
- OBJ/STL/PLY: geometry only (OBJ also keeps materials names); STL has no colour or UVs.
- USD: scene interchange; `.usdc` binary is smaller, `.usda` is readable.
- Modifiers are applied by default (`apply_modifiers`); Geometry Nodes instances are realised by the exporters.
