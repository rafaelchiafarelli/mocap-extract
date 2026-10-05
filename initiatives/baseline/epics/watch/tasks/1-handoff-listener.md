## 1. Hand-off listener (`mocap-extract watch`)

- **Depends on:** bootstrap/2; alignment; body/1; mocap-contracts v0.1.0 (messages-v0/7)
- **Contract:**
  - In: `TakeClosed` / `CameraFileReady` events (generated ZeroMQ receiver from `mocap_contracts`); the data root
  - Requires: each step starts as soon as its own inputs are verified (`check_file`), never on a take-level gate:
    - alignment: once `TakeClosed` and every role's timestamps are in
    - resampling + per-camera 2D: per role, once alignment is done and that role's video is in
    - triangulation, then quality: once every expected role is in
  - Delivers: `mocap-extract watch`, a long-running listener that dispatches those steps. On start-up and after any gap it **rescans the sidecars** (`take_state`), so a lost event or a restart only delays work and never loses it. Every step is idempotent (a finished step isn't rerun).
- **Pre-work:** none
- **Out of scope:** distributed workers (phase 2); GPU scheduling beyond one step at a time
- **Tests:** with fake steps: events in any order give the same step order; a restart halfway through resumes from the sidecars; a duplicate event runs nothing twice
