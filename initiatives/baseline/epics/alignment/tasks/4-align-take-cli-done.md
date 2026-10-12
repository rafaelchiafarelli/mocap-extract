## 4. Align one take from the command line

- **Depends on:** 1 (offsets and drift), 2 (resampling)
- **Contract:**
  - In: a take folder on the processing PC, as the recorder hands it off
    (`take.json`, `raw/<role>.timestamps.csv`, `prep/<role>.mkv`, each with its
    `.ready.json` sidecar)
  - Requires: nothing new. Wraps `compute_alignment` and `resample_role`
  - Delivers: `mocap-extract align TAKE_DIR`. It writes
    `extract/synced/<role>.mp4` for every role in `take.json` and prints one line
    per camera: offset (ms), drift (ppm), frames in and out, and every
    misaligned run. Exit 0 when every camera is written (misaligned runs are
    warnings), 1 when the take can't be aligned.
- **Decisions:**
  - Claude, for Rafael's review: the take is named by its folder path rather than
    a data root, session and take. `mocap-extract` has no config file yet, and
    the `watch` listener will call the same functions with paths it already knows.
  - Why now: the MVP (`mocap-studio/MVP-plan.md`) needs synced videos from a real
    take before `watch` exists.
- **Pre-work:** none
- **Out of scope:** the sync tolerance (task 3; it will turn misaligned runs into
  failures), `ExtractIndex` (body/2), the `watch` listener
- **Tests:** a two-camera synthetic take gives two synced videos with equal frame
  counts and exit 0; a take without END gives exit 1 and a message
