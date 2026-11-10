#!/usr/bin/env python3
"""Copy lib/gauge.py into every skill's scripts/ folder (each skill must be installable on its own).

Usage: python tools/sync_lib.py          copy
       python tools/sync_lib.py --check  exit 1 if any copy differs (used by tools/check_repo.py and CI)
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "lib" / "gauge.py"


def targets():
    return sorted(p / "scripts" / "gauge.py" for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").exists())


def main():
    check = "--check" in sys.argv
    src = SRC.read_bytes()
    stale = []
    for t in targets():
        if not t.exists() or t.read_bytes() != src:
            stale.append(t)
            if not check:
                t.parent.mkdir(exist_ok=True)
                t.write_bytes(src)
    if check:
        for t in stale:
            print("out of sync:", t.relative_to(ROOT))
        return 1 if stale else 0
    print(f"synced {len(targets())} skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
