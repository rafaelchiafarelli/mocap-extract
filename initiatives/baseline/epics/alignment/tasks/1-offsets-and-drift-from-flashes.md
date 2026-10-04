## 1. Offsets and drift from the flashes

- **Depends on:** bootstrap
- **Contract:**
  - In: `report.json` + timestamps
  - Requires: START flash frame = t0; END flash estimates per-camera drift
  - Delivers: `compute_alignment(take_dir) -> Alignment`
- **Pre-work:** none
- **Out of scope:** —
- **Tests:** synthetic data with known offset and drift
