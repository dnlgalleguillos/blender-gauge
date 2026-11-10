"""Gate mesh quality: n-gons, triangles, holes, inverted normals, duplicate/loose geometry, UV density.

Usage (live):  run_blender_script path=skills/gauge-modeling/scripts/mesh_gate.py args={"collection": "Props", "max_ngons": 0}
Usage (file):  python run_headless.py mesh_gate.py --blend asset.blend collection=Props require_closed=true
Args: collection (name of an object or collection; default whole scene), max_ngons, max_tris, require_closed (bool),
      require_uv (bool), max_texel_cv (float, e.g. 0.35), allow_boundary (bool, true).
Always-on checks: loose_verts, zero_area_faces, duplicate_verts, non_manifold_edges, inverted_volume.
Measures the evaluated mesh, so modifiers and Geometry Nodes count. Prints one GAUGE_JSON line, gate "mesh-health".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gauge

P = gauge.params(globals(), collection=None, max_ngons=None, max_tris=None, require_closed=False,
                 require_uv=False, max_texel_cv=None, allow_boundary=True)
r = gauge.Report("mesh-health")
objs = gauge.pick(P["collection"])
r.check("meshes_found", len(objs), len(objs) > 0, "> 0", "nothing to measure: check the collection name")
if objs:
    gauge.mesh_gate(r, objs, max_ngons=P["max_ngons"], max_tris=P["max_tris"], require_closed=P["require_closed"],
                    require_uv=P["require_uv"], max_texel_cv=P["max_texel_cv"], allow_boundary=P["allow_boundary"])
r.emit()
