"""Gallery 06: reference matching as a measured loop. Start from lighting that is deliberately wrong (3x too bright, blue tint)
and let gauge-reference tell us what to change, one correction per round, until the gate passes.

Usage: python ../skills/gauge-core/scripts/run_headless.py match_demo.py --blend _work/crate.blend [width=640 height=360 samples=24]
Writes _work/match_ref.png, match_0.png ... match_N.png and _work/match.json (numbers per round).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa: F401,F403

P = args_from_argv(width=640, height=360, samples=24, rounds=5)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = P["width"], P["height"]
lights = [o for o in bpy.data.collections["gauge_rig"].objects if o.type == "LIGHT"]
world = sc.world.node_tree.nodes["Background"]
good = {"energy": {o.name: o.data.energy for o in lights}, "color": {o.name: tuple(o.data.color) for o in lights},
        "world": (tuple(world.inputs["Color"].default_value), world.inputs["Strength"].default_value)}


def shot(name):
    return gauge.render(os.path.join(OUT, name), samples=P["samples"], percent=100)


ref_path = shot("match_ref.png")
ref = gauge.load_pixels(ref_path)
# the mistake: far too much light and a cold tint
for o in lights:
    o.data.energy *= 3.0
    o.data.color = (0.75, 0.85, 1.0)
world.inputs["Strength"].default_value *= 3.0
rounds = []
for i in range(int(P["rounds"])):
    path = shot(f"match_{i}.png")
    d = gauge.compare(gauge.load_pixels(path), ref)
    gate = call("gauge-reference", "ref_match.py", must_pass=False, image=path, reference=ref_path)
    rounds.append({"round": i, "image": os.path.basename(path), "pass": gate["pass"], "failed": gate["failed"], "delta": gate["info"]["delta"]})
    print(f"GALLERY round {i}: error {d['mean_abs_error']:.4f}  exposure {d['exposure_stops']:+.2f} stops  rgb {d['rgb_shift']}", flush=True)
    if gate["pass"]:
        break
    # apply the corrections the gate asked for: exposure first (multiply by 2**-stops), then the per-channel tint
    k = 2 ** (-d["exposure_stops"])
    for o in lights:
        o.data.energy *= k
    world.inputs["Strength"].default_value *= k
    st_img = gauge.image_stats(gauge.load_pixels(path), with_palette=False)["mean_rgb"]
    st_ref = gauge.image_stats(ref, with_palette=False)["mean_rgb"]
    lin = lambda v: gauge.to_linear(v)
    ratios = [lin(r_) / max(lin(i_), 1e-6) for r_, i_ in zip(st_ref, st_img)]
    norm = (0.2126 * ratios[0] + 0.7152 * ratios[1] + 0.0722 * ratios[2])
    tint = [x / norm for x in ratios]  # tint only: luminance is handled by the exposure step
    for o in lights:
        o.data.color = tuple(min(1.0, c * t) for c, t in zip(o.data.color, tint))
    c = world.inputs["Color"].default_value
    world.inputs["Color"].default_value = (min(1, c[0] * tint[0]), min(1, c[1] * tint[1]), min(1, c[2] * tint[2]), 1)
with open(os.path.join(OUT, "match.json"), "w") as fh:
    json.dump({"rounds": rounds, "samples": P["samples"], "start": "lights x3, colour (0.75, 0.85, 1.0), world x3"}, fh, indent=1)
