"""Gate scene hygiene: units, scale, names, collections, camera.

Usage (live):  run_blender_script path=skills/gauge-scene/scripts/scene_gate.py args={"allow_orphans": false}
Usage (file):  python run_headless.py scene_gate.py --blend scene.blend allow_orphans=false
Args: expect_unit_scale (float, 1.0), allow_default_names (bool, false), allow_orphans (bool, true).
Prints one GAUGE_JSON line, gate "scene-hygiene".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gauge

P = gauge.params(globals(), expect_unit_scale=1.0, allow_default_names=False, allow_orphans=True)
r = gauge.Report("scene-hygiene")
gauge.scene_gate(r, expect_unit_scale=P["expect_unit_scale"], allow_default_names=P["allow_default_names"],
                 allow_orphans=P["allow_orphans"])
r.emit()
