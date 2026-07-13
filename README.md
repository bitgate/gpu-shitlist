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

The JSON is a flat array of entries. Each entry has a `pattern` (regex or literal), the `fields` to match against, optional `conditions` (version gates), and an `action`:

```json
{
  "id": "powervr-vulkan-min-spec",
  "vendor": "Imagination Technologies",
  "match_type": "regex",
  "pattern": "PowerVR",
  "fields": ["gpu_name"],
  "action": "deny_vulkan",
  "conditions": {
    "min_vulkan_api": "1.1.170",
    "min_driver_version": "1.473.1397"
  },
  "reason": "Unity default blocklist: PowerVR Vulkan drivers below this threshold crash",
  "source": "unity"
}
```

Hard denies (e.g. `PowerVR.*GE8320`) simply omit `conditions` — match means deny, no version check.

Load it at startup, check your GPU string — C++ with [nlohmann/json](https://github.com/nlohmann/json) (ports 1:1 to C#, Kotlin, Java):

```cpp
#include <fstream>
#include <regex>
#include <sstream>
#include <vector>
#include <nlohmann/json.hpp>

static std::vector<int> parseVersion(const std::string& v) {
    std::vector<int> parts;
    std::stringstream ss(v);
    for (std::string p; std::getline(ss, p, '.');) parts.push_back(std::stoi(p));
    return parts;
}

static bool versionBelow(const std::string& actual, const std::string& minimum) {
    return parseVersion(actual) < parseVersion(minimum);
}

bool shouldDenyVulkan(const nlohmann::json& blocklist,
                      const std::string& gpuName,
                      const std::string& vulkanApi = "",
                      const std::string& driverVersion = "") {
    for (const auto& e : blocklist["entries"]) {
        bool matched = e["match_type"] == "regex"
            ? std::regex_search(gpuName, std::regex(e["pattern"].get<std::string>()))
            : gpuName == e["pattern"].get<std::string>();
        if (!matched) continue;

        if (!e.contains("conditions")) return true;
        const auto& c = e["conditions"];
        if (c.contains("min_vulkan_api") && !vulkanApi.empty() &&
            versionBelow(vulkanApi, c["min_vulkan_api"].get<std::string>())) return true;
        if (c.contains("min_driver_version") && !driverVersion.empty() &&
            versionBelow(driverVersion, c["min_driver_version"].get<std::string>())) return true;
    }
    return false;
}
```

```cpp
std::ifstream f("blocklist.json");
auto blocklist = nlohmann::json::parse(f);
if (shouldDenyVulkan(blocklist, gpuName, vulkanApiVersion, driverVersion))
    fallBackToGLES();
```

Same thing in Rust ([serde_json](https://crates.io/crates/serde_json) + [regex](https://crates.io/crates/regex)):

```rust
use regex::Regex;
use serde_json::Value;

fn parse_version(v: &str) -> Vec<u32> {
    v.split('.').filter_map(|p| p.parse().ok()).collect()
}

fn version_below(actual: &str, minimum: &str) -> bool {
    parse_version(actual) < parse_version(minimum)
}

fn should_deny_vulkan(blocklist: &Value, gpu_name: &str, vulkan_api: &str, driver_version: &str) -> bool {
    for e in blocklist["entries"].as_array().into_iter().flatten() {
        let pattern = e["pattern"].as_str().unwrap_or_default();
        let matched = if e["match_type"] == "regex" {
            Regex::new(pattern).map(|re| re.is_match(gpu_name)).unwrap_or(false)
        } else {
            gpu_name == pattern
        };
        if !matched {
            continue;
        }

        let Some(c) = e.get("conditions") else { return true };
        if let Some(min) = c["min_vulkan_api"].as_str() {
            if !vulkan_api.is_empty() && version_below(vulkan_api, min) {
                return true;
            }
        }
        if let Some(min) = c["min_driver_version"].as_str() {
            if !driver_version.is_empty() && version_below(driver_version, min) {
                return true;
            }
        }
    }
    false
}
```

```rust
let blocklist: Value = serde_json::from_str(&std::fs::read_to_string("blocklist.json")?)?;
if should_deny_vulkan(&blocklist, &gpu_name, &vulkan_api, &driver_version) {
    fall_back_to_gles();
}
```

No conditions = unconditional hard deny. Conditions present = deny only when the device's reported version is **below** the minimum.

One extra condition exists: `unless_driver_msb_set` (currently only on the Adreno entry). Qualcomm's newer drivers set the most significant bit of the raw `VkPhysicalDeviceProperties::driverVersion` — if you have that raw `uint32`, skip the entry when `driverVersion & 0x80000000` is set. If you only have version strings, ignoring it just makes the check slightly more conservative.

Desktop entries carry a `platform` field (`windows` / `linux`) — skip entries whose platform isn't yours. Entries without `platform` apply everywhere.

### Match fields

| Field | Source |
|---|---|
| `gpu_name` | `GL_RENDERER` / Vulkan physical device name (default) |
| `device_model` | Android `Build.MODEL` |
| `device_brand` | Android `Build.BRAND` |
| `device_product` | Android `Build.PRODUCT` |

## What's in the list

18 entries covering:

**From Unity's default Vulkan blocklist** ([official min-spec table](https://docs.unity3d.com/6000.0/Documentation/Manual/allow-deny-vulkan-usage.html)):

- **PowerVR** — Vulkan API < 1.1.170 or driver < 1.473.1397
- **Mali** — Vulkan API < 1.0.61
- **Adreno** — Vulkan API < 1.0.49, skipped when the raw driver version has its MSB set
- **NVidia** — Vulkan API < 1.0.13
- **Pixel 6 / 6 Pro / 6a** — regex hard deny on `device_model`/`device_product` (`oriole`/`raven`/`bluejay`), Unity denies the whole family by default

**From Flutter Impeller's Vulkan fallback** ([`DriverInfoVK::IsKnownBadDriver()`](https://github.com/flutter/flutter/blob/master/engine/src/flutter/impeller/renderer/backend/vulkan/driver_info_vk.cc)):

- **Adreno 650 and older** — hard deny; needs workarounds Impeller refuses to carry (660+ stays allowed)
- **Huawei Maleoon** — hard deny, all models
- **Samsung Xclipse** — deny when Vulkan API < 1.3 (first-gen Xclipse bug proxy; broken and fixed units report identical driver versions)
- **PowerVR pre-B-series (Rogue / A-series)** — hard deny; Impeller only trusts B-series and newer
- **Pixel 10** — deny below PowerVR DDK build 6794074 (driver 25.1) on `device_model`

**From Unreal Engine's driver deny list** (`Engine/Config/BaseHardware.ini`, UE5 `release`; desktop entries, tagged with `platform`):

- **NVIDIA** — Windows: Vulkan denied below driver 570.00 · Linux: denied below 580.00
- **AMD (Linux)** — Mesa/RADV below 25.0.0 denied
- **Intel** — Windows: Vulkan denied below unified driver 101.5989 · Linux: Mesa below 25.0.0 denied

Only Vulkan-relevant rules were ingested — D3D11/D3D12-only entries and rules gated on Unreal's internal `AdapterGeneration` / driver dates (not observable from a GPU string) were skipped.

**Community-sourced** (crash reports):

- **PowerVR Rogue GE8100/8300/8320** — unconditional hard denies

Every non-community entry is traceable to engine source or official docs — see the `source` field per entry.

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
    unless_driver_msb_set: true   # optional — skip entry when raw driver version MSB is set
  reason: "SIGSEGV on non-trivial Vulkan workloads"
  source: community
```

The generator validates (regex compiles, unique IDs, version strings parse), dedupes by pattern, sorts by vendor, and compiles to `output/blocklist.json`.
