## 2. Resampling to constant FPS

- **Depends on:** 1
- **Contract:**
  - In: `prep/<role>.mkv` from the recorder (variable FPS possible on STREAM devices)
  - Requires: FFmpeg; trim between the START and END sync markers; single target FPS
  - Delivers: `extract/synced/<role>.mp4` with the same frame count on every camera
- **Pre-work:** none
- **Out of scope:** —
- **Tests:** synthetic VFR → CFR video with the correct count
