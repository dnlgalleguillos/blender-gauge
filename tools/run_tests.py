#!/usr/bin/env python3
"""Run everything: static checks, then the headless Blender suites (one Blender launch per suite).

Usage: python tools/run_tests.py [filter]     filter = part of a suite name, e.g. materials
Blender is found from $BLENDER_EXE, else the newest ~/Downloads/blender-5* folder, else `blender` on PATH.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    flt = sys.argv[1] if len(sys.argv) > 1 else ""
    rc = subprocess.run([sys.executable, str(ROOT / "tools" / "check_repo.py")]).returncode
    if rc:
        return rc
    sys.path.insert(0, str(ROOT / "tests"))
    import unittest

    import test_skills
    suite = unittest.TestSuite()
    for name in unittest.TestLoader().getTestCaseNames(test_skills.InBlender):
        if flt in name:
            suite.addTest(test_skills.InBlender(name))
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if res.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
