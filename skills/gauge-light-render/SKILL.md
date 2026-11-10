---
name: gauge-light-render
description: Light, frame and render a Blender subject with measured results - rigs sized to the subject, camera distance solved for a target framing, render presets, turntables, and a render check for exposure, contrast, cropping and lights visible in shot. Use for lighting, camera, look development and final renders.
---

# Gauge light and render

Light and camera are set from the **subject's size**, then verified on a small render.

## 1. Frame
```
run_blender_script path=skills/gauge-light-render/scripts/frame_camera.py
  args={"subject":"Props","lens":85,"azimuth":25,"elevation":18,"fill":0.55,"aperture":2.8}
```
`fill` is the share of the frame the subject takes along its limiting side (width or height). The distance is solved by bisection, the camera looks at the subject centre, DoF focuses on it. Gate `camera-framing`: in front of the camera, not cropped, fit within limits. Longer lens (85-135 mm) for products and portraits, 24-35 mm for interiors.

## 2. Light
```
run_blender_script path=skills/gauge-light-render/scripts/rig.py args={"subject":"Props","preset":"three_point","ground":true}
```
| Preset | Character |
|---|---|
| `three_point` | key + fill + rim, general purpose |
| `softbox_product` | big top light and two strips, clean specular edges |
| `dramatic` | small hard key, rim, almost no fill |
| `overcast` | soft sky, no hard shadows |

Distances and sizes scale with the subject radius, powers with distance squared, `strength` scales all. Lights are invisible to the camera. Gate `light-rig` reports the key-to-fill ratio (useful range 0.8-12; 3-4 is natural).

## 3. Settings
`scripts/render_preset.py` with `preset` = `draft` (16 samples, 50 %), `preview` (64, 75 %), `final` (256, 100 %); Cycles with denoising and AgX. Gate `render-settings`.

## 4. Check
`scripts/render_check.py` renders and gates `render-check`: clipped whites <= 2 %, crushed blacks <= 10 %, contrast (p95-p5) >= 0.25, mean luma 0.12-0.75, subject fully in frame, no area light visible in shot. Add `reference` to also get the distance to another image. Run it headless on a saved copy: `python skills/gauge-core/scripts/run_headless.py skills/gauge-light-render/scripts/render_check.py --blend scene.blend subject=Props`.

## Turntable
`scripts/turntable.py` parents the camera to a pivot at the subject centre and turns it 360 degrees at constant speed; verified at the first, quarter and last frames and at `frame_end + 1`.

## Rules
- Big light sources = soft light. Size the key at roughly the subject's size, move it closer to soften.
- Always keep lights out of the camera's view; Blender 5.3 creates lights camera-invisible, the gate checks it anyway.
- AgX is the default view transform; if highlights still clip, lower the key before touching exposure.
- Final renders: save a copy, run headless, never from a live session (it blocks Blender, and a crash loses the scene).
- Wireframe look: Workbench ignores wireframe in renders; add a temporary Wireframe modifier instead.
