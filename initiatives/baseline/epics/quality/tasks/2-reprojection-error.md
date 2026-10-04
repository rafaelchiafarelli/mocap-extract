## 2. Reprojection error

- **Depends on:** 1
- **Contract:**
  - In: 3D + 2D + calibration
  - Requires: reprojection per camera and per point group
  - Delivers: `reproj_err_px` field per camera
- **Pre-work:** none
- **Out of scope:** —
- **Tests:** synthetic camera with known error
