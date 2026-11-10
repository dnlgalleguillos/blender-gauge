# Blender 5.x facts, measured

Checked by running them on Blender 5.3.0 Alpha (the suite in `tests/` re-checks the ones the library depends on).

- **Node trees exist by default.** `Material.node_tree` and `World.node_tree` are present on creation; `use_nodes` is deprecated (removal planned for 6.0). Do not set it.
- **Compositor:** `scene.compositing_node_group`, not `scene.node_tree`.
- **Geometry Nodes modifier inputs.** `mod["Socket_1"] = v` raises `TypeError`. Use `mod.properties.inputs[identifier]["value"]`; the first write must create the entry (`inputs[id] = {"value": v}`). `gauge.gn_set(mod, Size=2.0)` does this by input name.
- **Socket names, not identifiers.** `Map Range` takes `"From Min"`, not `"From_Min"`. Duplicated names (`Math` has two `Value`) need the identifier (`Value_001`). `gauge.node_build` tries the name, then the identifier.
- **Cycles:** `scene.cycles.feature_set` no longer exists; do not set it.
- **Dynamic enums under-report** when introspected (`render.engine` lists only EEVEE in a bare `-b` session, `view_settings.look` lists only `NONE`) although assignment of `CYCLES` or `AgX - Punchy` works. Assign inside `try/except` instead of checking membership.
- **Pixels:** `image.pixels` of an 8-bit PNG are the stored sRGB values; of a float/EXR image they are linear. `gauge.load_pixels` returns top row first.
- **Workbench ignores wireframe in final renders** (`shading.type='WIREFRAME'` is viewport only). For a wire look add a temporary Wireframe modifier and remove it after.
- **Modifier values after Geometry Nodes:** measure the *evaluated* object (`obj.evaluated_get(depsgraph)`); `obj.data` still holds the base mesh. `gauge.mesh_stats` already does this.
- **Instances are not objects.** Count them with `depsgraph.object_instances` (`gauge.instance_count`), and note that hiding the source object does not change the instance count.
- **Compression in glTF** (`meshopt`) needs `libmeshoptimizer.so`; tarball builds may not find it. `gauge-export` exports without compression by default.
