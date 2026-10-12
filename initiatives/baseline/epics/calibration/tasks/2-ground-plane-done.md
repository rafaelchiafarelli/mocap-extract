## 2. Ground plane

- **Depends on:** 1
- **Contract:**
  - In: frames with the board on the floor
  - Requires: FreeMoCap groundplane option
  - Delivers: origin/floor transform saved alongside the calibration
- **Decisions:**
  - Claude, for Rafael's review: the floor transform isn't a separate file. FreeMoCap folds it into the extrinsics in `calibration.toml` and sets `metadata.groundplane_calibration = true`. `calibrate()` reports whether it was set and, if not, FreeMoCap's reason (the board must hold still, under 1 mm/s, in some frames: lay it flat on the floor for ~3 s at the start of the take). A take without a still board still calibrates, just without the floor.
- **Pre-work:** none
- **Out of scope:** —
- **Tests:** Z axis perpendicular to the board in the fixture, and the board in z = 0 (`test_ground_plane_is_the_still_board`)
