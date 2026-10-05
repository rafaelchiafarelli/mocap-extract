## 1. FreeMoCap batch processing

- **Depends on:** calibration
- **Contract:**
  - In: synced videos + calibration
  - Requires: no GUI; per-camera 2D output and 3D
  - Delivers: body and hands 3D data and per-camera 2D in `extract/`, with the **per-camera 2D step callable on its own** (one role at a time) whenever FreeMoCap allows it, so `watch` can start each camera as it arrives
- **Pre-work:** check whether headless FreeMoCap 1.8.2 can run 2D tracking per camera separately from triangulation. If it can't without patching FreeMoCap, stop and flag it: the 2D step then runs once, after all roles have arrived.
- **Out of scope:** —
- **Tests:** runs on a short fixture take; 2D for one role alone matches that role's 2D from the full run
