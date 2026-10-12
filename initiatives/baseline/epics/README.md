# baseline — epics (execution order)

1. **bootstrap** — Skeleton and take intake (2 tasks)
2. **alignment** — Alignment (P3.1) (3 tasks: 1, 2, 4; task 3 moved to sync-tolerance)
3. **calibration** — Calibration (2 tasks)
4. **body** — Body and hands (P3.2) (2 tasks)
5. **quality** — Per-camera quality (bottleneck study) (5 tasks)
6. **watch** — Start processing as files arrive from the recorder (1 task)
7. **sync-tolerance** — Sync tolerance from the exposure time (1 task, formerly alignment/3). Separate epic so alignment can close: it fails any take without a read-back exposure time, so it waits for `mocap-capture` camera controls (studio-setup). Claude, for Rafael's review, 2026-10-12.

An epic only merges up into `epics` once all its tasks are `-done` and the suite is green.
