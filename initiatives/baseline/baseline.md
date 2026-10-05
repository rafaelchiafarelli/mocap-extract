# baseline — mocap-extract

**Goal:** P3, on the **processing PC** (all neural-net work runs here): align the videos, calibrate, run FreeMoCap (body + hands) and measure per-camera quality — the basis of the bottleneck study.

**Scope:** Batch processing, one take at a time, starting as soon as the recorder's files arrive (each one announced by a Harpia `CameraFileReady` event and verified against its sidecar). Every step can also run by hand. Per-camera metrics and ablation (remove one camera and measure the impact).

**Out of scope:** Face Landmarker, DeepFace, gaze (phase 2); distributed worker (phase 2).

**Initiative gate:** One take from the study protocol produces valid `index.json` and `quality.json` and a readable report.

General context, cross-repository order and open questions:
`mocap-studio/HANDOFF.md`.
