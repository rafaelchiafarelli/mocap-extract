## 1. ChArUco calibration

- **Depends on:** alignment
- **Contract:**
  - In: synced CALIBRATION take
  - Requires: FreeMoCap calibration with the board read from the take's `CalibrationBoard` (in `take.json`), using `measured_square_length_mm`; no board values in code
  - Delivers: `calibration.toml` in the session folder + calibration reprojection error
- **Decisions:**
  - Claude, for Rafael's review: FreeMoCap 1.8.2 only detects its own boards (5x3 or 7x5 squares, DICT_4X4_250, marker 0.8 of the square). Any other board in `take.json` is refused with the reason, before anything runs. That check is FreeMoCap's limit, not a board default.
  - Claude, for Rafael's review: camera 0 is pinned to the origin, then the board becomes the ground plane if FreeMoCap finds a still frame of it (task 2 verifies that). FreeMoCap also writes its .toml next to `extract/synced/` and into `~/freemocap_data`; the copy that counts is `<session>/calibration/calibration.toml`.
  - Claude, for Rafael's review: FreeMoCap discards its calibration error, so the reprojection error is measured again from the saved .toml: corners detected with FreeMoCap's own detector (skellytracker), triangulated, reprojected. It's reported overall and per camera, in px. The threshold is `--max-error-px` on the CLI (exit 2 above it), with no default.
  - FreeMoCap is imported through `mocap_extract.freemocap_import` (the 1.8.2 logging quirk).
- **Pre-work:** done with a synthetic fixture (`tests/synthetic_calibration.py`): pinhole cameras with known poses filming a moving board. The real calibration take is the MVP's step 2 (`mocap-studio/MVP-plan.md`).
- **Out of scope:** —
- **Tests:** runs on the fixture; error below a configurable threshold; distances between cameras recovered in mm (within 2 %); unsupported boards, non-CALIBRATION takes and missing synced videos refused
