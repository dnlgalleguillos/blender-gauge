"""Judge a render against a reference and say what to change, with numbers.

Usage:  python run_headless.py ref_match.py image=/tmp/render.png reference=/tmp/target.png
Args: image (your render), reference (target look), max_error (mean abs error limit, 0.08), max_exposure (stops, 0.35),
      max_tint (per-channel mean shift, 0.04), contrast_band ([0.85, 1.15]).
Gate "reference-match" passes when the render is within every limit. Each failed check carries an action in its hint:
exposure in stops (halve or double light by 2**stops), contrast ratio, tint direction. Change ONE thing, re-render, run again.
Stops are measured on the image as displayed (after the view transform, which compresses highlights), so a big mistake takes 2-3 rounds
to converge: apply the correction, re-render, measure again.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gauge

P = gauge.params(globals(), image=None, reference=None, max_error=0.08, max_exposure=0.35, max_tint=0.04,
                 contrast_band=[0.85, 1.15])
def main():
    r = gauge.Report("reference-match")
    if not (P["image"] and P["reference"] and os.path.exists(P["image"]) and os.path.exists(P["reference"])):
        r.check("inputs_exist", [P["image"], P["reference"]], False, "two readable images")
        r.emit()
        return
    d = gauge.compare(gauge.load_pixels(P["image"]), gauge.load_pixels(P["reference"]))
    r.info["delta"] = d
    st = d["exposure_stops"]
    factor = 2 ** (-st)
    r.check("exposure_stops", st, abs(st) <= P["max_exposure"], f"+-{P['max_exposure']}",
            f"render is {'brighter' if st > 0 else 'darker'} by {abs(st):.2f} stops: multiply every light and the world strength by {factor:.2f}")
    cr = d["contrast_ratio"]
    lo, hi = P["contrast_band"]
    r.check("contrast_ratio", cr, lo <= cr <= hi, f"{lo}..{hi}",
            "render has " + ("more" if cr > hi else "less") + " contrast: " + ("soften the key, raise fill" if cr > hi else
                                                                              "stronger key/fill ratio, darker background, or the 'AgX - Punchy' look"))
    names = ("red", "green", "blue")
    for i, nm in enumerate(names):
        t = d["rgb_shift"][i]
        r.check(f"tint_{nm}", t, abs(t) <= P["max_tint"], f"+-{P['max_tint']}",
                f"render has {'too much' if t > 0 else 'too little'} {nm}: adjust the light or world colour toward {'less' if t > 0 else 'more'} {nm}")
    r.check("mean_abs_error", d["mean_abs_error"], d["mean_abs_error"] <= P["max_error"], f"<= {P['max_error']}",
            "structure differs (framing, shapes, material colours): compare the two palettes with ref_report.py")
    r.check("luma_correlation", d["luma_correlation"], d["luma_correlation"] >= 0.8, ">= 0.8",
            "light and dark areas are not in the same places: check framing, light direction", severity="warn")
    r.emit()


main()
