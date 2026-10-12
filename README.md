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

## How it's used

```bash
mocap-extract align TAKE_DIR   # alignment: extract/synced/<role>.mp4 for every camera
mocap-extract calibrate TAKE_DIR [--max-error-px 1.0]   # CALIBRATION take -> <session>/calibration/calibration.toml
mocap-extract body TAKE_DIR    # PERFORMANCE take -> FreeMoCap 3D in extract/freemocap/ (a FreeMoCap recording folder)
mocap-extract watch            # planned, long-running: processes takes as they arrive
```

Every step can also be run by hand on one take.

## Development

```bash
make venv     # python3.12 venv in .venv, installs the package and FreeMoCap 1.8.2
make fixtures # FreeMoCap's test recording, used by the body tests (not committed)
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
(`mocap_extract.intake`: `check_file`, `take_state`).
alignment done: `alignment.compute_alignment` (offset and drift per camera) and
`resample.resample_role` (`extract/synced/<role>.mp4` at 30 fps, nearest frame,
warns past 33.3 ms), run on one take with `mocap-extract align`.
calibration/1 done: `calibration.calibrate` (FreeMoCap ChArUco calibration of a
CALIBRATION take, board from `take.json`, reprojection error overall and per
camera), run with `mocap-extract calibrate`; calibration/2 done (the still board is the
ground plane). body/1 done: `body.track_role` (2D, one camera) and
`body.reconstruct` (3D), run with `mocap-extract body`. Plan:
[`initiatives/baseline/`](initiatives/baseline/baseline.md). Dependencies:
`mocap-studio/DEPENDENCIES.md`.
