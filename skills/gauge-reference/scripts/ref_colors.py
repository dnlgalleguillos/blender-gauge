"""Read exact colours at chosen points of an image (a reference render or a screenshot).

Usage:  python run_headless.py ref_colors.py image=/tmp/ref.png points='[[0.5,0.5],[120,80]]'
Args: image, points (list of [x, y]; values <= 1.0 are fractions of width/height, larger values are pixels from the
      top-left), radius (px averaged around each point, 3).
Returns per point: sRGB hex (for the screenshot as seen) and linear RGB (for shader inputs). Prints one GAUGE_JSON line,
gate "ref-colors", with info.samples.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gauge

P = gauge.params(globals(), image=None, points=[[0.5, 0.5]], radius=3)
r = gauge.Report("ref-colors")
a = gauge.load_pixels(P["image"])
H, W = a.shape[:2]
out = []
for x, y in P["points"]:
    px = int(x * W) if x <= 1.0 else int(x)
    py = int(y * H) if y <= 1.0 else int(y)
    ok = 0 <= px < W and 0 <= py < H
    r.check(f"point_{x}_{y}_inside", [px, py], ok, f"0..{W - 1}, 0..{H - 1}")
    if not ok:
        continue
    rad = int(P["radius"])
    patch = a[max(0, py - rad):py + rad + 1, max(0, px - rad):px + rad + 1, :3].reshape(-1, 3).mean(0)
    srgb = "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in patch)
    out.append({"px": [px, py], "srgb_hex": srgb, "linear": [round(v, 4) for v in gauge.hex_to_linear(srgb)]})
r.info["samples"] = out
r.emit()
