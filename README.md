# gpu-shitlist

A community-maintained blocklist of GPUs with broken Vulkan drivers. Drop the JSON into your game client, check the GPU string, deny Vulkan on match, fall back to OpenGL ES.

Born because **PowerVR Rogue GPUs SIGSEGV on non-trivial Vulkan workloads** and their drivers will never be fixed. Seeded from Unity's default Vulkan blocklist + real-world crash reports.

## Get the blocklist

**Direct download (no clone needed):**

```
https://github.com/bitgate/gpu-shitlist/releases/latest/download/blocklist.json
```

Or grab a pinned version from the [releases page](https://github.com/bitgate/gpu-shitlist/releases).

## Use it

The JSON is a flat array of entries. Each entry has a `pattern` (regex or literal), the `fields` to match against, optional `conditions` (version gates), and an `action`. Load it at startup, check your GPU string:

```python
import json, re

with open("blocklist.json") as f:
    blocklist = json.load(f)["entries"]

def should_deny_vulkan(gpu_name, vulkan_api=None, driver_version=None):
    for entry in blocklist:
        field_values = {"gpu_name": gpu_name}
        targets = [field_values.get(f, "") for f in entry.get("fields", ["gpu_name"])]
        matched = any(
            re.search(entry["pattern"], t) if entry["match_type"] == "regex" else entry["pattern"] == t
            for t in targets
        )
        if not matched:
            continue
        conditions = entry.get("conditions")
        if conditions:
            if "min_vulkan_api" in conditions and vulkan_api and vulkan_api < conditions["min_vulkan_api"]:
                return True, entry
            if "min_driver_version" in conditions and driver_version and driver_version < conditions["min_driver_version"]:
                return True, entry
        else:
            return True, entry
    return False, None
```

No conditions = unconditional hard deny. Conditions present = deny only when the device's reported version is **below** the minimum.

### Match fields

| Field | Source |
|---|---|
| `gpu_name` | `GL_RENDERER` / Vulkan physical device name (default) |
| `device_model` | Android `Build.MODEL` |
| `device_brand` | Android `Build.BRAND` |
| `device_product` | Android `Build.PRODUCT` |

## What's in the list

8 entries covering:

- **PowerVR Rogue GE8100/8300/8320** — unconditional hard denies (community-sourced crash reports)
- **PowerVR** — Vulkan API < 1.1.170 or driver < 1.473.1397 (Unity default)
- **Mali** — Vulkan API < 1.0.61 (Unity default)
- **Adreno** — Vulkan API < 1.0.49 (Unity default)
- **NVidia** — Vulkan API < 1.0.13 (Unity default)
- **Pixel 6** — literal hard deny on `device_model` (Unity default)

## Contribute

Edit `sources/entries.yaml`, run the generator, commit the output:

```bash
pip install pyyaml
python generate.py           # generate output/blocklist.json
python generate.py --check   # validate only
python generate.py -v        # verbose summary
```

### Entry format

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

The generator validates (regex compiles, unique IDs, version strings parse), dedupes by pattern, sorts by vendor, and compiles to `output/blocklist.json`.
