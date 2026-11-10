---
name: gauge-core
description: Start here for any Blender task. Defines the measure-then-fix loop, how to run Gauge scripts (live through blender-mcp or headless), how to read a GAUGE_JSON verdict, and routes to the other gauge-* skills. Use before modeling, materials, Geometry Nodes, lighting, rendering or export.
---

# Gauge core

Blender work goes wrong silently: a bevel that did not apply, a texture in the wrong colour space, a subject cropped by the camera. Gauge replaces "looks fine" with **measurements**. Every skill ends in a gate script that prints one line:

```
GAUGE_JSON {"gate":"mesh-health","pass":false,"failed":["ngons"],"checks":[{"name":"ngons","value":12,"ok":false,"limit":"<= 0","hint":"triangulate or re-quad the n-gons"}],"info":{...}}
```

## The loop
1. **Snapshot** the scene before editing: `scripts/snapshot.py`.
2. **Build small.** One change, written to a `.py` file, idempotent (reuse objects by name).
3. **Gate.** Run the skill's gate script. Fix every failed check using its `hint`; `warn` checks are advice.
4. **Look.** Gates catch numbers, not taste. With blender-mcp use `look` (`angles` + `clay` for form, `camera` for the shot); headless, render small with `gauge.render()`.
5. Repeat until the gate passes and the picture is right, then finish with `gauge-export` if the asset leaves Blender.

## Running scripts
| Where | Command |
|---|---|
| Live Blender (blender-mcp) | `run_blender_script` with `path` and `args` (read as `SCRIPT_ARGS`) |
| Headless | `python skills/gauge-core/scripts/run_headless.py <script.py> key=value ... [--blend f.blend]` |

Never run heavy final renders in a live session (it freezes Blender and a crash loses the scene): save a copy, run headless. Parameters merge as defaults < `GAUGE_PARAMS` env < `SCRIPT_ARGS` < `key=value` after `--`.

## Routing
| Task | Skill |
|---|---|
| units, naming, collections, transforms | `gauge-scene` |
| meshes, bevels, props, mesh defects | `gauge-modeling` |
| materials, node graphs, textures | `gauge-materials` |
| procedural geometry, instancing | `gauge-geonodes` |
| lights, camera framing, render, exposure | `gauge-light-render` |
| copy a look from an image or node screenshot | `gauge-reference` |
| glTF / FBX / USD / OBJ / STL, budgets | `gauge-export` |

## Rules that save time
- Metres, Z-up, scale applied (`1 BU = 1 m`). Name everything; put generated work in one collection.
- Prefer the data API (`bpy.data`, `bmesh`) to `bpy.ops`: operators need UI context that scripts often lack.
- Read what you did not build before changing it: `gauge.node_text(tree)` or the MCP `get_node_tree`.
- The helper library is `scripts/gauge.py` (same file in every skill). Check `references/blender-5x-facts.md` for API behaviour verified on Blender 5.3 before trusting memory of older versions.
