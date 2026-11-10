"""Run every tests/in_blender/*_tests.py in headless Blender: one launch per file, one unittest each."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import blender_runner as br

HERE = pathlib.Path(__file__).resolve().parent / "in_blender"


def make(path):
    def t(self):
        out, err, rc = br.run(path, timeout=1500)
        res = br.suite_result(out)
        self.assertIsNotNone(res, f"no SUITE line\n{out[-1500:]}\n{err[-1500:]}")
        self.assertFalse(res["failed"], "\n".join(f"{k}:\n{v}" for k, v in res["failed"].items()))
        self.assertTrue(res["passed"], "no tests ran")
    return t


class InBlender(unittest.TestCase):
    pass


for f in sorted(HERE.glob("*_tests.py")):
    setattr(InBlender, f"test_{f.stem}", make(f))

if __name__ == "__main__":
    unittest.main(verbosity=2)
