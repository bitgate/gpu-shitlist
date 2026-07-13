#!/usr/bin/env python3
"""GPU Vulkan blocklist generator.

Reads source entries from sources/*.yaml, validates them, and compiles
the final blocklist as output/blocklist.json.

Usage:
    python generate.py              # generate output
    python generate.py --check      # validate only, no output
    python generate.py --verbose    # show all entries in summary
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

ROOT = Path(__file__).parent
SOURCES_DIR = ROOT / "sources"
OUTPUT_FILE = ROOT / "output" / "blocklist.json"

VALID_ACTIONS = {"deny_vulkan"}
VALID_MATCH_TYPES = {"regex", "literal"}
VALID_PLATFORMS = {"windows", "linux", "android"}
DEFAULT_FIELDS = ["gpu_name"]


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.strip().split("."))


def load_entries() -> list[dict]:
    entries = []
    for src in sorted(SOURCES_DIR.glob("*.yaml")):
        with open(src) as f:
            data = yaml.safe_load(f)
        if not data or "entries" not in data:
            continue
        for entry in data["entries"]:
            entry["_source_file"] = src.name
            entries.append(entry)
    return entries


def validate_entry(entry: dict, idx: int) -> list[str]:
    errors = []
    eid = entry.get("id", f"<index {idx}>")

    for field in ("id", "vendor", "match", "action", "reason"):
        if field not in entry:
            errors.append(f"[{eid}] missing required field: {field}")

    if errors:
        return errors

    match = entry["match"]
    if not isinstance(match, dict):
        errors.append(f"[{eid}] 'match' must be a mapping")
        return errors

    mtype = match.get("type")
    if mtype not in VALID_MATCH_TYPES:
        errors.append(f"[{eid}] invalid match type: {mtype} (must be {VALID_MATCH_TYPES})")

    pattern = match.get("pattern")
    if not pattern:
        errors.append(f"[{eid}] missing match.pattern")
    elif mtype == "regex":
        try:
            re.compile(pattern)
        except re.error as e:
            errors.append(f"[{eid}] invalid regex '{pattern}': {e}")

    if entry["action"] not in VALID_ACTIONS:
        errors.append(f"[{eid}] invalid action: {entry['action']} (must be {VALID_ACTIONS})")

    conditions = entry.get("conditions", {})
    if conditions:
        for key in ("min_vulkan_api", "min_driver_version"):
            if key in conditions:
                try:
                    parse_version(conditions[key])
                except (ValueError, TypeError):
                    errors.append(f"[{eid}] invalid {key}: {conditions[key]}")
        if "unless_driver_msb_set" in conditions and not isinstance(conditions["unless_driver_msb_set"], bool):
            errors.append(f"[{eid}] unless_driver_msb_set must be a boolean")

    platform = entry.get("platform")
    if platform is not None and platform not in VALID_PLATFORMS:
        errors.append(f"[{eid}] invalid platform: {platform} (must be {VALID_PLATFORMS})")

    return errors


def dedup_key(entry: dict) -> tuple:
    m = entry["match"]
    return (m["type"], m["pattern"], tuple(sorted(m.get("fields", DEFAULT_FIELDS))))


def compile_entry(entry: dict) -> dict:
    m = entry["match"]
    out = {
        "id": entry["id"],
        "vendor": entry["vendor"],
        "match_type": m["type"],
        "pattern": m["pattern"],
        "fields": m.get("fields", DEFAULT_FIELDS),
        "action": entry["action"],
    }
    if "conditions" in entry:
        out["conditions"] = entry["conditions"]
    out["reason"] = entry["reason"]
    if "source" in entry:
        out["source"] = entry["source"]
    return out


def generate(check_only: bool = False, verbose: bool = False) -> int:
    entries = load_entries()
    if not entries:
        print("No source entries found.")
        return 1

    all_errors = []
    seen_ids: set[str] = set()
    for i, entry in enumerate(entries):
        all_errors.extend(validate_entry(entry, i))
        eid = entry.get("id")
        if eid and eid in seen_ids:
            all_errors.append(f"[{eid}] duplicate id")
        seen_ids.add(eid)

    if all_errors:
        print(f"\n❌ {len(all_errors)} validation error(s):")
        for e in all_errors:
            print(f"  {e}")
        return 1

    seen_patterns: dict[tuple, str] = {}
    deduped = []
    for entry in entries:
        key = dedup_key(entry)
        if key in seen_patterns:
            print(f"  ⚠ duplicate pattern skipped: {entry['id']} (same as {seen_patterns[key]})")
            continue
        seen_patterns[key] = entry["id"]
        deduped.append(entry)

    deduped.sort(key=lambda e: (e["vendor"].lower(), e["id"]))
    compiled = [compile_entry(e) for e in deduped]

    output = {
        "version": str(date.today()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(compiled),
        "entries": compiled,
    }

    if check_only:
        print(f"✅ {len(compiled)} entries valid, no output written (--check)")
        return 0

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"✅ Generated {OUTPUT_FILE}")
    print(f"   {len(compiled)} entries from {len(set(e['_source_file'] for e in deduped))} source file(s)")
    print()

    by_vendor: dict[str, int] = {}
    for e in deduped:
        by_vendor[e["vendor"]] = by_vendor.get(e["vendor"], 0) + 1

    print("   By vendor:")
    for vendor, count in sorted(by_vendor.items()):
        print(f"     {vendor}: {count}")

    if verbose:
        print("\n   Entries:")
        for e in compiled:
            cond = ""
            if "conditions" in e:
                parts = []
                if "min_vulkan_api" in e["conditions"]:
                    parts.append(f"api≥{e['conditions']['min_vulkan_api']}")
                if "min_driver_version" in e["conditions"]:
                    parts.append(f"driver≥{e['conditions']['min_driver_version']}")
                cond = f" [{', '.join(parts)}]" if parts else ""
            print(f"     {e['match_type']:7s} {e['pattern']:40s}{cond}")

    return 0


def main():
    parser = argparse.ArgumentParser(description="GPU Vulkan blocklist generator")
    parser.add_argument("--check", action="store_true", help="validate only, don't write output")
    parser.add_argument("--verbose", "-v", action="store_true", help="show all entries in summary")
    args = parser.parse_args()
    sys.exit(generate(check_only=args.check, verbose=args.verbose))


if __name__ == "__main__":
    main()
