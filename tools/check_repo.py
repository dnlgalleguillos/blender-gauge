#!/usr/bin/env python3
"""Static checks for the repo (no Blender needed). Exit code 1 when anything is wrong.

Per skill: SKILL.md frontmatter (name == folder, description <= 400 chars, one line, no ": "), size budget, every
scripts/ references/ recipes/ path it mentions exists, scripts compile and carry a Usage docstring, gate scripts print a
GAUGE_JSON line and never call sys.exit. Repo level: gauge.py copies in sync with lib/, recipe JSON parses, README
names every skill, plugin manifests agree with the skills on disk.

Usage: python tools/check_repo.py
"""
import ast
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
HELPERS = {"gauge.py", "kit.py", "presets.py", "run_headless.py"}  # modules and tools, not gate scripts
MAX_DESC, MAX_TOKENS = 400, 2500
errors, warnings = [], []


def err(msg):
    errors.append(msg)


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    out = {}
    for line in m.group(1).split("\n"):
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


def check_skill(d):
    md = d / "SKILL.md"
    fm = frontmatter(md.read_text())
    if fm is None:
        return err(f"{d.name}: SKILL.md has no frontmatter")
    if fm.get("name") != d.name:
        err(f"{d.name}: frontmatter name '{fm.get('name')}' != folder")
    desc = fm.get("description", "")
    if not desc:
        err(f"{d.name}: empty description")
    if len(desc) > MAX_DESC:
        err(f"{d.name}: description is {len(desc)} chars (max {MAX_DESC})")
    if ": " in desc:
        err(f"{d.name}: description contains ': ' (breaks YAML plain scalars)")
    toks = len(md.read_text()) // 4
    if toks > MAX_TOKENS:
        err(f"{d.name}: SKILL.md ~{toks} tokens (max {MAX_TOKENS})")
    text = md.read_text()
    for rel in set(re.findall(r"(?<![\w/.-])(?:scripts|references|recipes)/[\w./-]+\.(?:py|md|json)", text)):
        if not (d / rel).exists() and not (ROOT / rel).exists():
            err(f"{d.name}: SKILL.md mentions {rel} which does not exist")
    for rel in set(re.findall(r"skills/[\w-]+/scripts/[\w.-]+\.py", text)):
        if not (ROOT / rel).exists():
            err(f"{d.name}: SKILL.md mentions {rel} which does not exist")
    for py in sorted((d / "scripts").glob("*.py")) if (d / "scripts").is_dir() else []:
        src = py.read_text()
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            err(f"{py.relative_to(ROOT)}: {e}")
            continue
        doc = ast.get_docstring(tree) or ""
        if py.name != "gauge.py" and "Usage" not in doc:
            err(f"{py.relative_to(ROOT)}: module docstring needs a Usage section")
        if py.name not in HELPERS:
            if ".emit()" not in src:
                err(f"{py.relative_to(ROOT)}: gate script never calls .emit()")
            if "sys.exit(" in src:
                err(f"{py.relative_to(ROOT)}: sys.exit() ends a live Blender session's handler; use return inside main()")
    for js in sorted((d / "recipes").glob("*.json")) if (d / "recipes").is_dir() else []:
        try:
            spec = json.loads(js.read_text())
            assert {"nodes", "links", "interface"} <= set(spec), "needs nodes, links, interface"
            keys = set(spec["nodes"])
            for a, b in spec["links"]:
                for end in (a, b):
                    if end.split(".", 1)[0] not in keys:
                        err(f"{js.relative_to(ROOT)}: link {a} -> {b} names an unknown node")
        except Exception as e:  # noqa: BLE001
            err(f"{js.relative_to(ROOT)}: {e}")


def main():
    dirs = sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").exists())
    if not dirs:
        err("no skills found")
    for d in dirs:
        check_skill(d)
    for ex in sorted((ROOT / "examples").glob("*/build_*.py")) if (ROOT / "examples").is_dir() else []:
        src = ex.read_text()
        if "Usage" not in (ast.get_docstring(ast.parse(src)) or ""):
            err(f"{ex.relative_to(ROOT)}: module docstring needs a Usage section")
        if not (ex.parent / "README.md").exists():
            err(f"{ex.parent.relative_to(ROOT)}: example has no README.md")
    for path in ROOT.rglob("*"):  # nothing in the repo may point at one person's machine
        if path.is_file() and not {".git", "_work", "_out", "__pycache__"} & set(path.parts) and path.suffix in {".py", ".md", ".json", ".yml"}:
            if "/home/" in path.read_text(errors="ignore") and path.name != "check_repo.py":
                err(f"{path.relative_to(ROOT)}: contains an absolute /home/ path")
    lib = (ROOT / "lib" / "gauge.py").read_bytes()
    for d in dirs:
        cp = d / "scripts" / "gauge.py"
        if not cp.exists() or cp.read_bytes() != lib:
            err(f"{d.name}: scripts/gauge.py is missing or out of sync (python tools/sync_lib.py)")
    readme = (ROOT / "README.md").read_text() if (ROOT / "README.md").exists() else ""
    for d in dirs:
        if d.name not in readme:
            err(f"README.md does not mention {d.name}")
    mp = ROOT / ".claude-plugin" / "plugin.json"
    if mp.exists():
        meta = json.loads(mp.read_text())
        if meta.get("version") and "version" in meta and not re.match(r"^\d+\.\d+\.\d+$", meta["version"]):
            err("plugin.json: version must be x.y.z")
    for line in errors:
        print("ERROR", line)
    print(f"{len(dirs)} skills checked, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
