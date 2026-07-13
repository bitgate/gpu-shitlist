# gpu-shitlist

GPU Vulkan blocklist generator. Compiles human-editable source entries into a final JSON blocklist that game clients use to deny Vulkan on broken GPUs and fall back to OpenGL ES.

## Usage

```bash
pip install pyyaml
python generate.py           # generate output/blocklist.json
python generate.py --check   # validate only
python generate.py -v        # verbose summary
```

## Adding entries

Edit `sources/entries.yaml`:

```yaml
- id: my-gpu-block
  vendor: Imagination Technologies
  match:
    type: regex          # or "literal"
    pattern: "PowerVR.*GE8320"
    fields: [gpu_name]   # optional, defaults to [gpu_name]
  action: deny_vulkan
  conditions:             # optional — omit for unconditional deny
    min_vulkan_api: "1.1.170"
    min_driver_version: "1.473.1397"
  reason: "SIGSEGV on non-trivial Vulkan workloads"
  source: community
```

### Match fields
- `gpu_name` — GL_RENDERER / Vulkan physical device name (default)
- `device_model` — Android `Build.MODEL`
- `device_brand` — Android `Build.BRAND`
- `device_product` — Android `Build.PRODUCT`

### Conditions
If `conditions` is present, the entry only triggers when the device's reported version is **below** the minimum. If absent, the match is an unconditional hard deny.

## Output

`output/blocklist.json` — the compiled blocklist. Load at startup, check the GPU renderer string against each entry's pattern, evaluate conditions if present, deny Vulkan on match.
