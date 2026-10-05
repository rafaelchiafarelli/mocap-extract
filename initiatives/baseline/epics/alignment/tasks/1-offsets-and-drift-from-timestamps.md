## 1. Offsets and drift from the timestamps

- **Depends on:** bootstrap
- **Contract:**
  - In: `take.json` (START/END `SyncEvent`s) + `report.json` + `raw/<role>.timestamps.csv` (frame, host_ts_ns), handed off at END
  - Requires: every camera's timestamps on the recorder's host clock; START marker = t0; per-camera offset = first frame vs t0; drift = measured vs nominal frame period between START and END
  - Delivers: `compute_alignment(take_dir) -> Alignment`
- **Pre-work:** none
- **Out of scope:** refinement from a visual marker (LED flash — parked, see `mocap-capture/initiatives/future/README.md`)
- **Tests:** synthetic data with known offset and drift
