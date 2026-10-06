## 2. Take intake (processing PC)

- **Depends on:** 1
- **Contract:**
  - In: a take folder filled file by file by the recorder (`mocap-capture` handoff), with its sidecars (`closed.json`, `<file>.ready.json`)
  - Requires: `TakeClosed`, `CameraFileReady` and `layout` from mocap-contracts
  - Delivers: `check_file(take_dir, rel_path)`, which verifies a file against its sidecar (size, sha256) before any step reads it, and `take_state(take_dir)`, which reports the roles expected, the files arrived and verified, and the files missing, all **from the sidecars on disk**. A file without a sidecar or that doesn't match it is never processed.
- **Pre-work:** none
- **Out of scope:** receiving the events (watch/1); copying files (recorder side)
- **Tests:** good file passes; missing sidecar, wrong size, wrong sha256 each refused; `take_state` of a half-arrived take lists exactly what's missing
