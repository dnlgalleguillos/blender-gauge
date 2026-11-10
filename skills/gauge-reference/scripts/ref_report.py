"""Measure an image: exposure, contrast, colour, palette, focus - and, with a reference, how far it is.

Usage (headless or live):  python run_headless.py ref_report.py image=/tmp/ref.png [reference=/tmp/mine.png]
Args: image (png/jpg/exr path), reference (second image to compare against; the deltas answer "image vs reference"),
      palette (swatch count, 5), focus (bool, true: 4x4 sharpness map).
Reports mean luma, p5/p95, contrast, clipping, saturation, mean RGB, palette as sRGB hex with shares, sharpness grid
(1.0 = sharpest cell). With a reference: mean_abs_error, exposure_stops (+ = image brighter), luma_shift, rgb_shift,
contrast_ratio, luma_correlation. Prints one GAUGE_JSON line, gate "reference-report".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gauge

P = gauge.params(globals(), image=None, reference=None, palette=5, focus=True)
def main():
    r = gauge.Report("reference-report")
    if not (P["image"] and os.path.exists(P["image"])):
        r.check("image_exists", P["image"], False, "a readable file")
        r.emit()
        return
    a = gauge.load_pixels(P["image"])
    st = gauge.image_stats(a)
    st["palette"] = gauge.palette(a, k=int(P["palette"]))
    r.info["image"] = st
    if P["focus"]:
        r.info["sharpness_grid"] = gauge.sharpness_grid(a)
    if P["reference"]:
        b = gauge.load_pixels(P["reference"])
        r.info["reference"] = gauge.image_stats(b)
        r.info["delta"] = gauge.compare(a, b)
    r.check("image_loaded", st["size"], True)
    r.emit()


main()
