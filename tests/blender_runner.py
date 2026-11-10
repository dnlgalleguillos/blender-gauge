"""Run a script in headless Blender and return its output. Used by every test module.

Blender is found from $BLENDER_EXE, else the newest ~/Downloads/blender-*/blender, else `blender` on PATH.
"""
import glob
import json
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent


def find_blender():
    exe = os.environ.get("BLENDER_EXE")
    if exe:
        return exe
    cands = sorted(glob.glob(os.path.expanduser("~/Downloads/blender-5.3*/blender")))
    cands += sorted(glob.glob(os.path.expanduser("~/Downloads/blender-5*/blender")))
    return cands[0] if cands else "blender"


def blender_env(exe):
    env = dict(os.environ)
    lib = pathlib.Path(exe).resolve().parent / "lib"
    if lib.is_dir():
        env["LD_LIBRARY_PATH"] = f"{lib}:{env.get('LD_LIBRARY_PATH', '')}"
    return env


def run(script, args=None, blend=None, timeout=600):
    """Run `script` with `args` (words after --). Returns (stdout, stderr, returncode)."""
    exe = find_blender()
    cmd = [exe, "-b", "--factory-startup"]
    if blend:
        cmd.append(str(blend))
    cmd += ["--python-exit-code", "1", "--python", str(script)]
    if args:
        cmd += ["--"] + [f"{k}={json.dumps(v) if not isinstance(v, str) else v}" for k, v in args.items()]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=blender_env(exe))
    return p.stdout, p.stderr, p.returncode


def gauge_lines(stdout):
    return [json.loads(l.split("GAUGE_JSON ", 1)[1]) for l in stdout.splitlines() if l.startswith("GAUGE_JSON ")]


def suite_result(stdout):
    m = re.search(r"^SUITE (\{.*\})$", stdout, re.M)
    return json.loads(m.group(1)) if m else None
