# baseline — mocap-extract

**Goal:** P3: align the videos, calibrate, run FreeMoCap (body + hands) and measure per-camera quality — the basis of the bottleneck study.

**Scope:** Batch processing, one take at a time. Per-camera metrics and ablation (remove one camera and measure the impact).

**Out of scope:** Face Landmarker, DeepFace, gaze (phase 2); distributed worker (phase 2).

**Initiative gate:** One take from the study protocol produces valid `index.json` and `quality.json` and a readable report.

General context, cross-repository order and open questions:
`mocap-studio/HANDOFF.md`.
