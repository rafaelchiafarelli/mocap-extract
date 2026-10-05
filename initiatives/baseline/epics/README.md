# baseline — epics (execution order)

1. **bootstrap** — Skeleton and take intake (2 tasks)
2. **alignment** — Alignment (P3.1) (2 tasks)
3. **calibration** — Calibration (2 tasks)
4. **body** — Body and hands (P3.2) (2 tasks)
5. **quality** — Per-camera quality (bottleneck study) (5 tasks)
6. **watch** — Start processing as files arrive from the recorder (1 task)

An epic only merges up into `epics` once all its tasks are `-done` and the suite is green.
