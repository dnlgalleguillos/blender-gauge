"""Tiny in-Blender test collector: @test registers, run() prints one SUITE line the runner parses."""
import json
import traceback

_TESTS = []


def test(fn):
    _TESTS.append(fn)
    return fn


def run():
    passed, failed = [], {}
    for fn in _TESTS:
        try:
            fn()
            passed.append(fn.__name__)
        except BaseException:  # SystemExit from a script under test must be reported, not end the run
            failed[fn.__name__] = traceback.format_exc(limit=4)
    print("SUITE " + json.dumps({"passed": passed, "failed": failed}))


def run_script(path, **args):
    """Execute a skill script exactly as run_blender_script would (SCRIPT_ARGS set) and return its gates."""
    import contextlib
    import io
    import os
    import runpy
    import sys
    buf = io.StringIO()
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    try:
        with contextlib.redirect_stdout(buf):
            runpy.run_path(path, init_globals={"SCRIPT_ARGS": args}, run_name="__main__")
    finally:
        sys.path.pop(0)
    out = buf.getvalue()
    gates = [json.loads(l.split("GAUGE_JSON ", 1)[1]) for l in out.splitlines() if l.startswith("GAUGE_JSON ")]
    return gates, out
