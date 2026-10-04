## 2. Resampling to constant FPS

- **Depends on:** 1
- **Contract:**
  - In: raw videos (MKV/MP4, including variable FPS from the tablets)
  - Requires: FFmpeg; trim between the flashes; single target FPS
  - Delivers: `extract/synced/<role>.mp4` with the same frame count on every camera
- **Pre-work:** none
- **Out of scope:** —
- **Tests:** synthetic VFR → CFR video with the correct count
