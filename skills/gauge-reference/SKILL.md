---
name: gauge-reference
description: Recreate a look from a reference image or node-editor screenshots in Blender, then measure the match - palette, exposure in stops, contrast, tint, focus, structure - and get numeric corrections. Includes safe workspace begin/end and a headless node-tree reader. Use when asked to copy, match or replicate an image or shader/Geometry Nodes screenshot.
---

# Gauge reference

"Make it look like this" is only finished when a **number** says so. This skill turns a reference into measurements, builds in an isolated collection, and compares every render against the target.

## Authority order
1. What the user wrote (explicit values and rules).
2. Node screenshots: they decide *connections and settings*.
3. The reference render: it decides *appearance*.
Anything you infer rather than read is an assumption: list it in your reply and let the user confirm.

## Workflow
1. **Begin** an isolated workspace: `scripts/workspace.py action=begin name=match1` (saves camera, world, engine, view settings; creates the collection).
2. **Read the screenshots** with `references/reading-node-screenshots.md`: write the graph as text (node, key values, links) before building. Small numbers in a screenshot are easy to misread; flag the uncertain ones.
3. **Measure the reference**: `scripts/ref_report.py image=ref.png` gives mean luma, contrast, clipping, saturation, a palette of sRGB hex with shares and a 4x4 sharpness map (where the focus is). `scripts/ref_colors.py` reads exact colours at points; the hex is what you see, `linear` is what goes into a shader.
4. **Build** the nodes with `gauge.node_build` / `gauge.gn_make` (see gauge-materials, gauge-geonodes), then re-read what you built with `scripts/node_text.py` and compare it with your transcription.
5. **Render small**, then `scripts/ref_match.py image=mine.png reference=ref.png`. Each failed check carries one correction with a number: exposure in stops (multiply light by 2^-stops), contrast ratio, tint per channel, structural error.
6. **Change one thing**, render, measure again. Stop when the gate passes (defaults: exposure within 0.35 stops, contrast ratio 0.85-1.15, tint within 0.04, error <= 0.08).
7. **End**: `workspace.py action=end` restores the scene and *lists* what it would delete; pass `confirm=true` only when the user agrees.

## Tools
| Script | Answers |
|---|---|
| `ref_report.py` | what is in this image (and how far is it from another) |
| `ref_colors.py` | exact colour at a point |
| `ref_match.py` | is my render close enough, and what to change |
| `node_text.py` | what does this material / group / world / compositor tree contain |
| `workspace.py` | begin / end without leaving a mess |

## Rules
- Match structure first (framing, shapes, light direction), colour second, detail last.
- Fix exposure before colour: a 1-stop error shifts every colour measurement.
- A render at 50 % size and 24 samples is enough to judge all of the above.
- Reference images with compression or a different gamma are not exact: trust the palette and ratios, not single pixels.
