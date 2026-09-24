# Working notes

- Sources: `sources/*.yaml`; generated artifact: `output/blocklist.json`. README documents generation via `python generate.py` and validation via `python generate.py --check`.
- Checked 2026-09-24: all 18 generated entries use `deny_vulkan`; no WebGPU-specific entries or Construct/PlayCanvas sources are present.
- Existing `impeller-pixel10-powervr-ddk-min` in `sources/impeller.yaml` matches `^Pixel 10\b` against `device_model`, including Pixel 10 Pro, and denies Vulkan below DDK build `6794074`. This is conditional, not a blanket Pixel 10 ban or evidence that newer drivers are free of WebGPU bugs.
- Latest task was a coverage check only; no blocklist rules changed.
