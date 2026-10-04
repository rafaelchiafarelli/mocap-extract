# Initiatives

The full process (initiative → epic → task → contract, branch chain, per-task
loop, stop-and-ask rules) lives in the **mocap-workflow** skill
(`.claude/skills/mocap-workflow/SKILL.md`). Read it before anything else.

Rules specific to this repository:

- **Layout:** `initiatives/<initiative>/epics/<epic>/tasks/<n>-<task>.md`.
  The number is the implementation order, and the file name is the branch name.
- **Done marker:** `-done` suffix on the **file name** (`git mv` in a separate
  commit, right after the implementation commit). Never a status line.
- **Order between epics:** in `initiatives/<initiative>/epics/README.md`.
- **Order between repositories:** in `mocap-studio/HANDOFF.md`.
- **Test suite:** `pytest` at the root (Python repositories) or
  `pio test -e native` (mocap-sync-fw). "Not broken" = green suite.
- **Contracts between repositories** only through the `mocap-contracts` package
  and the session folder layout. Never import code from another mocap repository.
  A change that crosses repositories starts in `mocap-contracts`.

## Index

| Initiative | Status |
|---|---|
| [baseline](baseline/baseline.md) | Planned — not started |
