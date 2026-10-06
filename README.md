# mocap-extract

P3, **on the processing PC**: turns a take's synchronised videos into 3D body
and hand motion. It's the only place neural networks run (FreeMoCap,
MediaPipe, GPU). It also produces the per-camera quality metrics the camera
bottleneck study is based on.

## Where it sits in the architecture

```
recorder (mocap-capture) ──files + Harpia ZeroMQ events──▶ mocap-extract ──extract/index.json──▶ mocap-adapt
```

- **Intake / `watch`:** listens for the recorder's `TakeClosed` and
  `CameraFileReady` events, verifies every file against its sidecar (size,
  sha256), and starts each step as soon as its own inputs are in. A lost event
  or a restart is recovered by rescanning the sidecars.
- **Alignment (3.1):** offsets and drift from the per-frame host
  timestamps, then resampling to one constant fps
- **Calibration:** ChArUco calibration of every camera plus the ground plane
- **Body and hands (3.2):** FreeMoCap, 2D per camera then 3D
- **Quality (3.3):** detection rate, jitter, reprojection error, bone
  stability, and an ablation that removes one camera at a time

It writes `extract/` in the take folder: synced videos, calibration, 2D/3D
data, `index.json` (`ExtractIndex`) and `quality.json`/`quality.md`.

## How it's used (planned)

```bash
mocap-extract watch      # long-running: processes takes as they arrive
```

Every step can also be run by hand on one take.

## Development

```bash
make venv     # python3.12 venv in .venv, installs the package and FreeMoCap 1.8.2
make test     # full suite
.venv/bin/mocap-extract --version
```

FreeMoCap's headless entry point is
`freemocap.core_processes.process_motion_capture_videos.process_recording_headless`
(pass `run_blender=False, make_jupyter_notebook=False`). Two quirks of 1.8.2:

- Importing it while the root logger already has handlers fails with a circular
  import. Import FreeMoCap before configuring logging, or in its own process.
- Importing it with no handlers installs its own TRACE-level console handler
  and writes a log file under `~/freemocap_data/logs_info_and_settings/`.

## Status

bootstrap done: package skeleton, CLI, FreeMoCap environment (Python 3.12,
torch 2.8.0+cu128, `mocap-contracts` v0.2.1) and take intake
(`mocap_extract.intake`: `check_file`, `take_state`). Plan:
[`initiatives/baseline/`](initiatives/baseline/baseline.md). Dependencies:
`mocap-studio/DEPENDENCIES.md`.
