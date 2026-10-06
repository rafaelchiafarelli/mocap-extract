## 1. FreeMoCap batch processing

- **Depends on:** calibration
- **Contract:**
  - In: synced videos + calibration
  - Requires: no GUI; per-camera 2D output and 3D
  - Delivers: body and hands 3D data and per-camera 2D in `extract/`, with the **per-camera 2D step callable on its own** (one role at a time) whenever FreeMoCap allows it, so `watch` can start each camera as it arrives
- **Pre-work:** done (2026-10-06): **yes, without patching.** On FreeMoCap's own test recording (3 cameras, 222 frames, its calibration toml), 2D run one camera at a time with `skellytracker.process_folder_of_videos.process_list_of_videos(video_paths=[one_video], ...)`, stacked on axis 0, saved to `data_2d_npy_file_path`, then `process_recording_folder` with `tracking_parameters_model.run_image_tracking = False`, gives 2D and 3D **identical** (max |diff| 0.0) to the stock all-cameras run. Things body/1 must handle:
  - Axis-0 order of the stacked 2D must be the camera order of the calibration toml (FreeMoCap uses the sorted video file names). Make the role order explicit; never rely on a directory listing.
  - The per-video call also writes annotated videos and its own `.npy` under the output path given; point both inside `extract/`.
  - Same MediaPipe Holistic tracker and parameters on both paths (CPU; about 50 s for 3 × 222 frames).
- **Out of scope:** —
- **Tests:** runs on a short fixture take; 2D for one role alone matches that role's 2D from the full run
