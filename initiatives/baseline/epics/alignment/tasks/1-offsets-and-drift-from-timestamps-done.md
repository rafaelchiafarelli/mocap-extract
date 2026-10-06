## 1. Offsets and drift from the timestamps

- **Depends on:** bootstrap
- **Contract:**
  - In: `take.json` (START/END `SyncEvent`s) + `report.json` + `raw/<role>.timestamps.csv` (frame, host_ts_ns), handed off at END
  - Requires: every camera's timestamps on the recorder's host clock; START marker = t0; per-camera offset = first frame vs t0; drift = measured vs nominal frame period between START and END
  - Delivers: `compute_alignment(take_dir) -> Alignment`
- **Decisions (Claude, for Rafael's review, 2026-10-06):**
  - `report.json` is **not** read. Handoff/3 sends it after `TakeClosed` and says it doesn't gate processing, and watch/1 starts alignment on `TakeClosed` + timestamps. Everything it summarises (frames, gaps, measured fps) is recomputed from the timestamps.
  - Window = frames with START <= `host_ts_ns` <= END. Offset = first frame in the window minus t0. Drift = least-squares period over frame *slots* (a dropped frame counts as round(step / median step) slots) vs the nominal `CameraConfig.fps` in `take.json`, in ppm; positive = slower than declared.
  - Timestamps are read only after `check_file` verifies them. `Alignment` is a Python dataclass, not a contract message: `CameraAlignment.frames_out` needs the target FPS, which comes with task 2.
- **Pre-work:** none
- **Out of scope:** refinement from a visual marker (LED flash — parked, see `mocap-capture/initiatives/future/README.md`)
- **Tests:** synthetic data with known offset and drift
