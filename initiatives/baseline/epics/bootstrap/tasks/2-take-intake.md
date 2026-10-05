## 2. Take intake (processing PC)

- **Depends on:** 1
- **Contract:**
  - In: a take folder handed off by the recorder (`mocap-capture` handoff/2)
  - Requires: `TakeManifest` (`manifest.json`) from mocap-contracts; `layout`
  - Delivers: `check_take(take_dir)`, which every `mocap-extract` command runs first. A take without a manifest, or with a missing file or a wrong sha256, is refused with the list of bad files and never processed.
- **Pre-work:** none
- **Out of scope:** copying takes (recorder side)
- **Tests:** good take passes; missing manifest, missing file, corrupted file each refused
