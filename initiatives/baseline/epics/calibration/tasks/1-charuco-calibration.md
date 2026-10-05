## 1. ChArUco calibration

- **Depends on:** alignment
- **Contract:**
  - In: synced CALIBRATION take
  - Requires: FreeMoCap calibration with the board read from the take's `CalibrationBoard` (in `take.json`), using `measured_square_length_mm`; no board values in code
  - Delivers: `calibration.toml` in the session folder + calibration reprojection error
- **Pre-work:** Rafael prints the board and records a calibration take (real fixture) — procedure in `mocap-capture/initiatives/studio-setup/`
- **Out of scope:** —
- **Tests:** runs on the fixture; error below a configurable threshold
