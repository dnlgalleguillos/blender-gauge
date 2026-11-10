"""Shared helpers for the gallery scenes: call a skill script exactly like run_blender_script would, and log its gate."""
import contextlib
import io
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "lib"))
for sk in ("gauge-modeling", "gauge-materials", "gauge-geonodes", "gauge-light-render"):
    sys.path.append(os.path.join(ROOT, "skills", sk, "scripts"))

import bpy  # noqa: E402

import gauge  # noqa: E402

OUT = os.path.join(HERE, "_work")
os.makedirs(OUT, exist_ok=True)


def args_from_argv(**defaults):
    return gauge.params({}, **defaults)


def call(skill, script, must_pass=True, **args):
    """Run skills/<skill>/scripts/<script> with args; returns its first gate dict."""
    path = os.path.join(ROOT, "skills", skill, "scripts", script)
    buf = io.StringIO()
    sys.path.insert(0, os.path.dirname(path))
    try:
        with contextlib.redirect_stdout(buf):
            runpy.run_path(path, init_globals={"SCRIPT_ARGS": args}, run_name="__main__")
    finally:
        sys.path.pop(0)
    gates = gauge.parse(buf.getvalue())
    gate = gates[0]
    print(f"GALLERY {'PASS' if gate['pass'] else 'FAIL'} {gate['gate']} ({skill}/{script})", flush=True)
    if must_pass and not gate["pass"]:
        for c in gate["checks"]:
            if not c["ok"] and c.get("severity") != "warn":
                print("   x", c["name"], c["value"], c.get("limit"), c.get("hint", ""), flush=True)
        raise SystemExit(f"gate failed: {gate['gate']}")
    return gate


def write_gate(name, gates):
    with open(os.path.join(OUT, f"{name}.json"), "w") as fh:
        json.dump(gates, fh, indent=1)


def base_scene(width, height):
    gauge.clear_scene()
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    return sc
