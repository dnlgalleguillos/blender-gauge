# Blender Gauge: instructions for agents working in this repo

Skills for AI agents working in Blender 5.x. Each skill builds something and ends in a **gate**: a script that measures the result and prints one `GAUGE_JSON {...}` line (`pass`, `failed`, `checks` with value / limit / hint, `info`).

## Layout
- `skills/gauge-*/SKILL.md` + `scripts/` (+ `recipes/`, `references/`): one folder per skill, installable on its own.
- `lib/gauge.py`: the only shared module. Every skill carries a synced copy in `scripts/gauge.py`.
- `tests/in_blender/*_tests.py`: one headless Blender launch per file; `tests/test_skills.py` wraps them for unittest.
- `gallery/`: scenes that produce the README renders using only the skills' scripts; `tools/` repo tooling.

## Commands
```
python tools/sync_lib.py          # after editing lib/gauge.py
python tools/check_repo.py        # static checks, no Blender needed
python tools/run_tests.py [name]  # checks + Blender suites (BLENDER_EXE or ~/Downloads/blender-5*)
python gallery/build_gallery.py [--quick]
```

## Rules
- Edit `lib/gauge.py`, never a copy; then sync.
- A gate script prints exactly one `GAUGE_JSON` line through `Report.emit()`, returns early inside `main()` and never calls `sys.exit` (it would end a live Blender session's handler).
- Failed checks need a `hint` that says what to change. Use `severity="warn"` for advice.
- Verify every API claim on a running Blender before writing it in a SKILL.md; put verified behaviour in `skills/gauge-core/references/blender-5x-facts.md`.
- Keep each SKILL.md under ~2.5k tokens and each description under 400 characters, one line, no `: `.
- Every new script needs a Usage docstring and a test in the matching `tests/in_blender/` file. A gate that cannot fail is not a gate: test the failing case too.
- Heavy renders belong in headless runs, never in a live session.
