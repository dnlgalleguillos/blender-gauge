#!/usr/bin/env python3
"""Run a Gauge script in headless Blender and print a short verdict (works outside Blender).

Usage: python run_headless.py <script.py> [key=value ...] [--blend scene.blend] [--timeout 600]

Finds Blender from $BLENDER_EXE, else the newest ~/Downloads/blender-*/blender, else `blender` on PATH.
Prints one line per gate (PASS/FAIL), then each failed check with its limit and hint. Exit code 1 when
any gate failed or Blender crashed, so it can sit in a CI step. Use the blender-mcp `run_blender_script`
tool instead when a live Blender session is open (same scripts, same GAUGE_JSON line).
"""
import glob
import json
import os
import pathlib
import subprocess
import sys

MARK = "GAUGE_JSON "


def find_blender():
    if os.environ.get("BLENDER_EXE"):
        return os.environ["BLENDER_EXE"]
    found = sorted(glob.glob(os.path.expanduser("~/Downloads/blender-*/blender")), reverse=True)
    return found[0] if found else "blender"


def main(argv):
    blend, timeout, words = None, 600, []
    it = iter(argv)
    for a in it:
        if a == "--blend":
            blend = next(it)
        elif a == "--timeout":
            timeout = int(next(it))
        else:
            words.append(a)
    if not words:
        print(__doc__)
        return 2
    script, kv = words[0], words[1:]
    exe = find_blender()
    cmd = [exe, "-b", "--factory-startup"] + ([blend] if blend else []) + ["--python-exit-code", "1", "--python", script]
    if kv:
        cmd += ["--"] + kv
    env = dict(os.environ)
    lib = pathlib.Path(exe).resolve().parent / "lib"
    if lib.is_dir():
        env["LD_LIBRARY_PATH"] = f"{lib}:{env.get('LD_LIBRARY_PATH', '')}"
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    gates = [json.loads(l[len(MARK):]) for l in p.stdout.splitlines() if l.startswith(MARK)]
    other = [l for l in p.stdout.splitlines() if not l.startswith(MARK) and l.strip()
             and not l.startswith(("Blender ", "Read ", "Warning:", "Info:"))]
    bad = p.returncode != 0
    for g in gates:
        print(("PASS " if g["pass"] else "FAIL ") + g["gate"])
        for c in g["checks"]:
            if not c["ok"] and c.get("severity") != "warn":
                print(f"  x {c['name']} = {c['value']}  (limit {c.get('limit')})" + (f"  -> {c['hint']}" if c.get("hint") else ""))
        for c in g["checks"]:
            if not c["ok"] and c.get("severity") == "warn":
                print(f"  ! {c['name']} = {c['value']}" + (f"  -> {c['hint']}" if c.get("hint") else ""))
        bad = bad or not g["pass"]
    if not gates:
        print("no GAUGE_JSON line produced")
        bad = True
    for l in other[-12:]:
        print("   ", l)
    if p.returncode != 0:
        print(p.stderr[-1500:])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
