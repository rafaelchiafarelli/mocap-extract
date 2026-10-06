## 2. Resampling to constant FPS

- **Depends on:** 1
- **Contract:**
  - In: `prep/<role>.mkv` from the recorder (variable FPS possible on STREAM devices)
  - Requires: FFmpeg; trim between the START and END sync markers; single target FPS
  - Delivers: `extract/synced/<role>.mp4` with the same frame count on every camera
- **Decisions:**
  - Rafael, 2026-10-06: **nearest frame** (no blending): output frame n at t0 + n / fps takes the real frame nearest in host time. **Target 30 fps.** **Warn** whenever the frame used is more than one frame time at 30 fps (33.3 ms) off, whatever the target: logged and returned as runs of output frames.
  - Claude, for Rafael's review: the 30 fps target is a mocap-extract constant (`resample.TARGET_FPS`) for now, recorded later in `ExtractIndex.fps`, not a contract field. Output is H.264 `-crf 10`, `yuv420p`, written to a `.part` file and renamed. Video frame i = timestamps row i (preprocess keeps one output frame per input frame); a count mismatch is refused.
- **Pre-work:** none
- **Out of scope:** —
- **Tests:** synthetic VFR → CFR video with the correct count
