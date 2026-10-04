## 1. Per-camera 2D metrics

- **Depends on:** body
- **Contract:**
  - In: per-camera 2D
  - Requires: detection rate (body, left hand, right hand), 2D jitter during a static segment (T-pose)
  - Delivers: partial `CameraQuality` per camera
- **Pre-work:** none
- **Out of scope:** —
- **Tests:** synthetic data with known noise
