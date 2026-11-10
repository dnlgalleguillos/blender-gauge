#!/usr/bin/env python3
"""Install the skills for an agent by copying (or linking) them into its skills folder.

Usage: python tools/install.py [--dest DIR] [--link] [--uninstall] [--only a,b]
Default destination: ~/.claude/skills (Claude Code). Other agents read their own folder, e.g. ~/.agents/skills.
--link makes symlinks so edits in this repo show up immediately; --uninstall removes only what this script installed
(folders whose name starts with 'gauge-' and that contain a SKILL.md).
"""
import argparse
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(pathlib.Path.home() / ".claude" / "skills"))
    ap.add_argument("--link", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    dest = pathlib.Path(a.dest).expanduser()
    names = [p.name for p in sorted((ROOT / "skills").iterdir()) if (p / "SKILL.md").exists()]
    if a.only:
        names = [n for n in names if n in a.only.split(",")]
    for n in names:
        target = dest / n
        if a.uninstall:
            if target.is_symlink():
                target.unlink()
                print("removed link", target)
            elif target.is_dir() and (target / "SKILL.md").exists():
                shutil.rmtree(target)
                print("removed", target)
            continue
        dest.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            print("exists, skipped:", target, "(remove it first or use --uninstall)")
            continue
        if a.link:
            target.symlink_to(ROOT / "skills" / n, target_is_directory=True)
        else:
            shutil.copytree(ROOT / "skills" / n, target)
        print("installed", target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
