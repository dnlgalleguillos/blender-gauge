"""Material presets as node specs (see gauge.node_build). Each preset is a function (color, **kw) -> spec.

Usage:
    import presets
    mat = presets.make("mat_steel", "brushed_metal", color="#b9bec6", Roughness=0.3)

`color` is an sRGB hex string; extra keyword arguments override Principled BSDF inputs by name
("Roughness", "Metallic", "Coat Weight", ...). Procedural presets use object coordinates, so they need no UVs.
"""
import bpy
import gauge

BSDF = "ShaderNodeBsdfPrincipled"
OUT = {"type": "ShaderNodeOutputMaterial", "at": [900, 0]}


def _core(bsdf_in, extra_nodes=None, extra_links=None):
    nodes = {"bsdf": {"type": BSDF, "at": [600, 0], "in": bsdf_in}, "out": OUT}
    links = [["bsdf.BSDF", "out.Surface"]]
    nodes.update(extra_nodes or {})
    links += extra_links or []
    return {"nodes": nodes, "links": links}


def metal(color="#b9bec6", **kw):
    return _core({"Base Color": color, "Metallic": 1.0, "Roughness": 0.3, **kw})


def brushed_metal(color="#b9bec6", **kw):
    nodes = {
        "coord": {"type": "ShaderNodeTexCoord", "at": [-600, 0]},
        "map": {"type": "ShaderNodeMapping", "at": [-400, 0], "in": {"Scale": [1.0, 90.0, 90.0]}},
        "streaks": {"type": "ShaderNodeTexNoise", "at": [-200, 0], "set": {"noise_dimensions": "3D"},
                    "in": {"Scale": 4.0, "Detail": 6.0, "Roughness": 0.6}},
        "ramp": {"type": "ShaderNodeMapRange", "at": [20, 120], "in": {"From Min": 0.3, "From Max": 0.7, "To Min": 0.22, "To Max": 0.42}},
        "bump": {"type": "ShaderNodeBump", "at": [300, -160], "in": {"Strength": 0.04, "Distance": 0.002}},
    }
    links = [["coord.Object", "map.Vector"], ["map.Vector", "streaks.Vector"], ["streaks.Fac", "ramp.Value"],
             ["ramp.Result", "bsdf.Roughness"], ["streaks.Fac", "bump.Height"], ["bump.Normal", "bsdf.Normal"]]
    return _core({"Base Color": color, "Metallic": 1.0, "Anisotropic": 0.55, **kw}, nodes, links)


def plastic(color="#c8352b", **kw):
    return _core({"Base Color": color, "Roughness": 0.38, "Specular IOR Level": 0.5, "Coat Weight": 0.3,
                  "Coat Roughness": 0.1, **kw})


def ceramic(color="#e8ecef", **kw):
    return _core({"Base Color": color, "Roughness": 0.14, "Specular IOR Level": 0.6, "Coat Weight": 0.6,
                  "Coat Roughness": 0.03, **kw})


def rubber(color="#212123", **kw):
    nodes = {
        "coord": {"type": "ShaderNodeTexCoord", "at": [-500, 0]},
        "grain": {"type": "ShaderNodeTexNoise", "at": [-300, 0], "in": {"Scale": 220.0, "Detail": 3.0}},
        "bump": {"type": "ShaderNodeBump", "at": [100, -150], "in": {"Strength": 0.25, "Distance": 0.001}},
    }
    links = [["coord.Object", "grain.Vector"], ["grain.Fac", "bump.Height"], ["bump.Normal", "bsdf.Normal"]]
    return _core({"Base Color": color, "Roughness": 0.82, **kw}, nodes, links)


def glass(color="#f4fbff", **kw):
    return _core({"Base Color": color, "Roughness": 0.02, "IOR": 1.45, "Transmission Weight": 1.0, **kw})


def emissive(color="#ffb347", strength=8.0, **kw):
    return _core({"Base Color": "#000000", "Emission Color": color, "Emission Strength": strength, **kw})


def wood(color="#a8703c", **kw):
    dark = _shade(color, 0.55)
    nodes = {
        "coord": {"type": "ShaderNodeTexCoord", "at": [-800, 0]},
        "map": {"type": "ShaderNodeMapping", "at": [-600, 0], "in": {"Scale": [1.0, 6.0, 40.0]}},
        "warp": {"type": "ShaderNodeTexNoise", "at": [-400, -250], "in": {"Scale": 2.5, "Detail": 4.0, "Distortion": 0.3}},
        "rings": {"type": "ShaderNodeTexWave", "at": [-200, 0],
                  "set": {"wave_type": "BANDS", "bands_direction": "Y", "wave_profile": "SAW"},
                  "in": {"Scale": 3.0, "Distortion": 5.0, "Detail": 2.0}},
        "ramp": {"type": "ShaderNodeValToRGB", "at": [80, 0],
                 "set": {"color_ramp": {"interpolation": "EASE", "stops": [[0.1, list(gauge.hex_to_linear(dark)) + [1]],
                                                                          [0.9, list(gauge.hex_to_linear(color)) + [1]]]}}},
        "bump": {"type": "ShaderNodeBump", "at": [320, -200], "in": {"Strength": 0.12, "Distance": 0.003}},
    }
    links = [["coord.Object", "map.Vector"], ["map.Vector", "rings.Vector"], ["warp.Fac", "rings.Phase Offset"],
             ["rings.Fac", "ramp.Fac"], ["ramp.Color", "bsdf.Base Color"], ["rings.Fac", "bump.Height"],
             ["bump.Normal", "bsdf.Normal"], ["coord.Object", "warp.Vector"]]
    return _core({"Roughness": 0.52, "Coat Weight": 0.15, "Coat Roughness": 0.25, **kw}, nodes, links)


def concrete(color="#8b8c8a", **kw):
    dark = _shade(color, 0.62)
    nodes = {
        "coord": {"type": "ShaderNodeTexCoord", "at": [-700, 0]},
        "big": {"type": "ShaderNodeTexNoise", "at": [-450, 120], "in": {"Scale": 3.0, "Detail": 8.0, "Roughness": 0.65}},
        "fine": {"type": "ShaderNodeTexNoise", "at": [-450, -160], "in": {"Scale": 90.0, "Detail": 6.0, "Roughness": 0.7}},
        "mix": {"type": "ShaderNodeMix", "at": [-150, 0], "set": {"data_type": "FLOAT"}, "in": {"Factor": 0.35}},
        "ramp": {"type": "ShaderNodeValToRGB", "at": [80, 60],
                 "set": {"color_ramp": {"interpolation": "LINEAR", "stops": [[0.35, list(gauge.hex_to_linear(dark)) + [1]],
                                                                            [0.7, list(gauge.hex_to_linear(color)) + [1]]]}}},
        "bump": {"type": "ShaderNodeBump", "at": [320, -200], "in": {"Strength": 0.3, "Distance": 0.004}},
    }
    links = [["coord.Object", "big.Vector"], ["coord.Object", "fine.Vector"], ["big.Fac", "mix.A"], ["fine.Fac", "mix.B"],
             ["mix.Result", "ramp.Fac"], ["ramp.Color", "bsdf.Base Color"], ["fine.Fac", "bump.Height"],
             ["bump.Normal", "bsdf.Normal"]]
    return _core({"Roughness": 0.9, **kw}, nodes, links)


def _shade(hexcolor, k):
    lin = [v * k for v in gauge.hex_to_linear(hexcolor)]
    return gauge.linear_to_hex(lin)


PRESETS = {"metal": metal, "brushed_metal": brushed_metal, "plastic": plastic, "ceramic": ceramic, "rubber": rubber,
           "glass": glass, "emissive": emissive, "wood": wood, "concrete": concrete}


def spec(preset, color=None, **overrides):
    if preset not in PRESETS:
        raise KeyError(f"unknown preset '{preset}' (have: {sorted(PRESETS)})")
    fn = PRESETS[preset]
    return fn(color, **overrides) if color else fn(**overrides)


def make(name, preset, color=None, **overrides):
    """Create (or rebuild in place) material `name` from a preset. Existing users keep the same datablock."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    gauge.node_build(mat.node_tree, spec(preset, color, **overrides))
    return mat
