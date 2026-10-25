"""Enable, disable or inspect the nonsecret Ultra flags. Never reads config.json."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_INDENT = 2
sys.path.insert(0, str(ROOT))
from ultra import DEFAULT_CONFIG, Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "disable", "adaptive-enable", "adaptive-disable", "status"))
    args = parser.parse_args()
    settings, notice = Settings.read(DEFAULT_CONFIG)
    if notice:
        parser.error("ultra.json is invalid. Restore or repair that nonsecret settings file first.")
    if args.action != "status":
        values = dict(settings.__dict__)
        if args.action.startswith("adaptive-"):
            values["adaptive_routing_enabled"] = args.action == "adaptive-enable"
        else:
            values["enabled"] = args.action == "enable"
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=ROOT, prefix=".ultra-", suffix=".tmp", delete=False) as handle:
                name = handle.name
                json.dump(values, handle, indent=JSON_INDENT)
                handle.write("\n")
            os.replace(name, DEFAULT_CONFIG)
        finally:
            if name is not None:
                Path(name).unlink(missing_ok=True)
        settings, _ = Settings.read(DEFAULT_CONFIG)
    print("Ultra " + ("ON" if settings.enabled else "OFF")
          + f" | up to {settings.max_workers} workers | {settings.worker_retries} retries | "
          + f"{settings.worker_timeout_s}s per worker | {settings.max_escalations} escalation")
    print("Adaptive routing " + ("ON" if settings.adaptive_routing_enabled else "OFF")
          + f" | {settings.model_call_limit} model attempts per request | "
          + f"{settings.observed_token_limit} observed-token guard")


if __name__ == "__main__":
    main()
