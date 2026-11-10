---
name: gauge-scene
description: Keep a Blender scene clean and measurable - metric units, applied scale, real names, named collections, no orphan data. Gates scene hygiene and tidies it safely (dry run first). Use when starting from someone else's file, before exporting, or when scale and naming look wrong.
---

# Gauge scene

A tidy scene makes every later measurement trustworthy: modifiers behave with applied scale, exporters find named things, a 2 m door really is 2 m.

## Gate
`scripts/scene_gate.py` -> gate `scene-hygiene`. Fails on: non-metric units, unit scale != 1, negative scale, no camera in a render scene. Warns on: default names (`Cube.001`, `Material`), unapplied scale, objects loose in the Scene Collection, orphans (with `allow_orphans=false`).

```
run_blender_script path=skills/gauge-scene/scripts/scene_gate.py args={"allow_orphans": false}
```
Args: `expect_unit_scale` (1.0), `allow_default_names` (false), `allow_orphans` (true).

## Tidy
`scripts/tidy.py` never changes anything unless `apply=true`; without it, it lists what it would do:

| Step | What it does | Skips |
|---|---|---|
| `units` | metric, scale 1.0, metres | - |
| `scale` | bakes object scale into the mesh | shared mesh data, objects with children, negative scale |
| `organize` | moves loose objects into `Meshes` / `Lights` / `Cameras` / `Other` collections | objects already in a named collection |
| `purge` | removes datablocks with zero users | everything with a user |

```
run_blender_script path=skills/gauge-scene/scripts/tidy.py args={"steps": ["units","scale","organize"], "apply": true}
```
Re-run `scene_gate.py` after. Renaming is a judgement call: do it yourself with meaningful names (`bolt_M6`, `mat_brushed_steel`), the scripts only report.

## Rules
- 1 Blender unit = 1 metre; model at real size, scale the *camera and lights* to the subject, not the subject to the camera.
- Apply scale before Bevel, Array-with-offset, physics, or export; mirror modifiers need positive scale.
- One collection per asset or per generated system (`WavyCubes`, `Props`); to remove generated work later use `gauge.workspace_remove(name)` (dry run) then `confirm=True`.
- Never purge or delete in a user's live scene without asking: `purge` and `workspace_remove` exist for scenes you created.
