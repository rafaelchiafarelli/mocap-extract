## 4. Camera ablation

- **Depends on:** 2; 3
- **Contract:**
  - In: 2D + calibration
  - Requires: re-triangulate without each camera, one at a time
  - Delivers: change in 3D and in stability for each removed camera
- **Pre-work:** none
- **Out of scope:** —
- **Tests:** synthetic noisy camera: removing it improves the result
