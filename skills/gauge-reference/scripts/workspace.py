"""Work on a reference match without leaving a mess: begin, then end (restores the scene, dry-run removal by default).

Usage (live):  run_blender_script path=skills/gauge-reference/scripts/workspace.py args={"action": "begin", "name": "match1"}
               ... build inside collection "match1" ...
               run_blender_script path=... args={"action": "end", "name": "match1"}                  (dry run: lists what would go)
               run_blender_script path=... args={"action": "end", "name": "match1", "confirm": true} (restores and deletes)
Args: action (begin | end), name (collection, "match"), confirm (bool, false), keep_collection (bool, false: restore only).
begin saves camera, world, engine, resolution, view transform and samples in the scene, then creates the collection and makes it active.
end puts all of that back; the collection is only deleted with confirm=true and only objects inside it. Gate "workspace".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import gauge

P = gauge.params(globals(), action="begin", name="match", confirm=False, keep_collection=False)
r = gauge.Report("workspace")
sc = bpy.context.scene
if P["action"] == "begin":
    if "gauge_prev" in sc:
        r.check("not_already_begun", True, False, "begin once", "run action=end first (state is already saved)", severity="warn")
    else:
        gauge.state_save(sc)
    col = gauge.workspace_make(P["name"])
    r.info["collection"] = col.name
    r.check("collection_ready", col.name, True)
elif P["action"] == "end":
    restored = gauge.state_restore(sc)
    r.check("state_restored", bool(restored), bool(restored), True, "no saved state: begin was not run", severity="warn")
    if not P["keep_collection"]:
        res = gauge.workspace_remove(P["name"], confirm=bool(P["confirm"]))
        r.info["removal"] = res
        if res.get("found") and not P["confirm"]:
            r.check("removal_is_dry_run", res["objects"][:12], True, "pass confirm=true to delete")
else:
    r.check("action_valid", P["action"], False, "begin | end")
r.emit()
