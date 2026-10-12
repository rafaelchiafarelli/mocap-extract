## 3. Sync tolerance from the exposure time

- **Depends on:** 1 (offsets and drift), 2 (resampling); `take.json` with the
  camera control results recorded by `mocap-capture` (camera-controls)
- **Contract:**
  - In: `take.json` (per-camera control results), the aligned timeline
  - Requires: Rafael's rule (2026-10-12): the inter-camera sync error may be
    at most **one shutter (exposure) time**. The tolerance is the **shortest
    exposure time among the body cameras** in that take (conservative), read
    back from the device, never assumed. It replaces the fixed 33.3 ms warning.
    A camera without a read-back exposure time is an error, not a default.
    Exceeding the tolerance fails alignment with a report naming the cameras
    and the measured error. It's the signal to rethink the timestamp strategy.
  - Delivers: `align()` reports the tolerance, its source camera, and the
    measured worst error, and fails beyond it
- **Pre-work:** confirm the control key that carries exposure for the STREAM
  cameras (Camera2 `SENSOR_EXPOSURE_TIME`, in ns) in a real `take.json`
- **Out of scope:** changing the timestamp strategy itself
- **Tests:** within tolerance passes; just beyond fails; missing exposure is an
  error; the tolerance uses the shortest exposure
