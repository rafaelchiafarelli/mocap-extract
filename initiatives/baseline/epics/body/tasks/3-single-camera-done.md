## 3. Single-camera 3D

- **Depends on:** —
- **Contract:**
  - In: one video file (any fps), an optional time window (seconds)
  - Requires: MediaPipe Pose (the legacy solution bundled in the `mediapipe` wheel, model complexity 1: no download), its **world landmarks** (metres, hips-centred, camera axes)
  - Delivers: `mocap-extract mono VIDEO TAKE_DIR [--start S] [--end S]` writes `TAKE_DIR/extract/freemocap/output_data/mediapipe_body_3d_xyz.npy` (frames × 33 × 3, mm, 30 fps) and NaN hand arrays with FreeMoCap's names, plus `mono.json` (source, window, frames). That's the shape `mocap-blender` reads
- **Decisions:**
  - Claude, for Rafael's review, 2026-10-12: a test and preview path for when only one camera exists (Rafael's test clips). Depth is MediaPipe's estimate, not triangulated, so motion towards or away from the camera is weak. Frames are resampled to 30 fps (nearest frame) and smoothed with FreeMoCap's own filter settings (Butterworth, 4th order, 7 Hz, zero phase). No hands: MediaPipe Pose has no fingers; `mocap-blender` orients the hands from the pose's index, pinky and thumb points.
  - There's no `take.json` and no calibration: the output isn't a recorded take.
- **Pre-work:** none
- **Out of scope:** hands and face from one camera, using it for real shots
- **Tests:** on one camera of FreeMoCap's test recording: the frame count at 30 fps, every body point present, shoulder width 0.25–0.5 m
