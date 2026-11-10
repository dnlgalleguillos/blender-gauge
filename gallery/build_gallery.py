#!/usr/bin/env python3
"""Render the whole gallery from scratch: every image is produced by the skills' own scripts and gated.

Usage: python gallery/build_gallery.py [--quick] [--only crate,terrain,...]
--quick renders at 640x360 with 16 samples (a minute or two); the default is 1280x720, 96 samples.
Writes assets/gallery/*.jpg, assets/gallery/gates.json (every gate result) and assets/gallery/match.jpg (the measured loop).
Needs Blender (BLENDER_EXE or ~/Downloads/blender-*) and ImageMagick (`magick`).
"""
import glob
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = ROOT / "gallery" / "_work"
OUT = ROOT / "assets" / "gallery"
RUN = ROOT / "skills" / "gauge-core" / "scripts" / "run_headless.py"
SCENES = ["materials", "crate", "terrain", "radial", "scatter"]


def blender_run(script, *words, blend=None):
    cmd = [sys.executable, str(RUN), str(script)] + list(words) + (["--blend", str(blend)] if blend else []) + ["--timeout", "3000"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write("".join(f"    {l}\n" for l in p.stdout.splitlines() if "GALLERY" in l or "render  " in l or l.startswith(("FAIL", "PASS")) or "x " in l))
    if p.returncode != 0 and "GALLERY" not in p.stdout:
        print(p.stdout[-1500:], p.stderr[-1500:])
    return p


def to_jpg(src, dst, quality=90):
    subprocess.run(["magick", str(src), "-quality", str(quality), str(dst)], check=True)


def main():
    quick = "--quick" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].split(",")
    w, h, samples = (640, 360, 16) if quick else (1280, 720, 96)
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    gates = {}
    for name in SCENES:
        if only and name not in only:
            continue
        print(f"== {name}")
        png = WORK / f"{name}.png"
        if name == "materials":
            blender_run(ROOT / "skills" / "gauge-materials" / "scripts" / "swatch_sheet.py", f"out={png}", f"samples={samples}",
                        f"width={w}", f"height={h}")
        else:
            blender_run(ROOT / "gallery" / f"scene_{name}.py", f"out={png}", f"width={w}", f"height={h}", f"samples={samples}")
        if png.exists():
            to_jpg(png, OUT / f"{name}.jpg")
        gj = WORK / f"{name}.json"
        if gj.exists():
            gates[name] = json.loads(gj.read_text())
    if (not only or "match" in only) and (WORK / "crate.blend").exists():
        print("== match")
        blender_run(ROOT / "gallery" / "match_demo.py", f"width={min(w, 640)}", f"height={min(h, 360)}", f"samples={min(samples, 24)}",
                    blend=WORK / "crate.blend")
        mj = WORK / "match.json"
        if mj.exists():
            m = json.loads(mj.read_text())
            panels = [("reference", WORK / "match_ref.png", "")]
            for r in m["rounds"]:
                d = r["delta"]
                tag = "start" if r["round"] == 0 else f"round {r['round']}"
                panels.append((f"{tag}", WORK / r["image"], f"error {d['mean_abs_error']:.3f}   {d['exposure_stops']:+.2f} stops" + ("   PASS" if r["pass"] else "")))
            cmds = []
            for title, path, cap in panels:
                tile = WORK / f"tile_{title.replace(' ', '_')}.png"
                subprocess.run(["magick", str(path), "-resize", "480x270", "-background", "#14172e", "-gravity", "North", "-splice", "0x34",
                                "-fill", "#ffffff", "-pointsize", "20", "-annotate", "+0+6", title,
                                "-gravity", "South", "-splice", "0x30", "-fill", "#7cf0dc", "-pointsize", "17", "-annotate", "+0+6", cap, str(tile)], check=True)
                cmds.append(str(tile))
            subprocess.run(["magick", "montage"] + cmds + ["-tile", "3x", "-geometry", "+6+6", "-background", "#14172e", str(WORK / "match.png")], check=True)
            to_jpg(WORK / "match.png", OUT / "match.jpg")
            gates["match"] = m
    for name in SCENES:  # always publish every scene's latest result, even after a partial --only run
        gj = WORK / f"{name}.json"
        if gj.exists():
            gates[name] = json.loads(gj.read_text())
    if (WORK / "match.json").exists():
        gates["match"] = json.loads((WORK / "match.json").read_text())
    if gates:  # published file: no absolute paths from the machine that rendered it
        text = json.dumps(gates, indent=1).replace(str(ROOT) + "/", "").replace(str(pathlib.Path.home()) + "/", "~/")
        (OUT / "gates.json").write_text(text)
    print("done:", ", ".join(sorted(p.name for p in OUT.glob("*"))))


if __name__ == "__main__":
    main()
