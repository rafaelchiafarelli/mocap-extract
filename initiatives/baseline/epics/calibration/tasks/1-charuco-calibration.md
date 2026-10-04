## 1. ChArUco calibration

- **Depends on:** alignment
- **Contract:**
  - In: synced CALIBRATION take
  - Requires: FreeMoCap calibration with the board parameters
  - Delivers: `calibration.toml` in the session folder + calibration reprojection error
- **Pre-work:** Rafael prints the board and records a calibration take (real fixture)
- **Out of scope:** —
- **Tests:** runs on the fixture; error below a configurable threshold
