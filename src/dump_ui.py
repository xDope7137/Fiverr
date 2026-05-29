"""UI dumper for the Fiverr Android app.

Connects via uiautomator2 over ADB, captures the current screen (screenshot
+ XML hierarchy + unique resource-ids + context), and writes everything to
a timestamped folder under `dumps/`. Use this to inspect Fiverr screens
when adding new automation: manually navigate the phone to the target
screen, then run this script.

Reads `serial` from `config.json`; CLI flags override.

Usage:
    python dump_ui.py [--serial IP:PORT] [--label NAME] [--output-dir DIR]
"""
import argparse
import os
import re
import sys
from datetime import datetime

import uiautomator2 as u2

from config_util import resolve_serial

FIVERR_PACKAGE = "com.fiverr.fiverr"


def connect(serial):
    try:
        return u2.connect(serial)
    except Exception as e:
        print(f"[ERROR] Could not connect to device: {e}", file=sys.stderr)
        print("[HINT] Is `adb devices` showing your phone? "
              "For wireless ADB set `serial` in config.json or pass --serial.",
              file=sys.stderr)
        sys.exit(1)


def dump(device, label, output_dir):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(output_dir, f"{label}_{timestamp}")
    os.makedirs(folder, exist_ok=True)

    screenshot_path = os.path.join(folder, "screen.jpg")
    device.screenshot(screenshot_path)

    xml = device.dump_hierarchy()
    xml_path = os.path.join(folder, "layout.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)

    ids = sorted(set(re.findall(r'resource-id="([^"]+)"', xml)))
    ids_path = os.path.join(folder, "resource_ids.txt")
    with open(ids_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ids))

    current = device.app_current()
    context_path = os.path.join(folder, "context.txt")
    with open(context_path, "w", encoding="utf-8") as f:
        f.write(f"label: {label}\n")
        f.write(f"timestamp: {timestamp}\n")
        f.write(f"package: {current.get('package')}\n")
        f.write(f"activity: {current.get('activity')}\n")

    return folder, current, len(ids)


def main():
    parser = argparse.ArgumentParser(description="Dump the current Android screen UI for the Fiverr app.")
    parser.add_argument("--serial", default=None,
                        help="Override serial / IP:PORT from config.json.")
    parser.add_argument("--label", default="screen",
                        help="Short name for this dump (e.g. inbox, conversation, compose). Default: 'screen'.")
    parser.add_argument("--output-dir", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dumps"),
                        help="Root folder for dump output. Default: dumps/ in the project root.")
    args = parser.parse_args()

    device = connect(resolve_serial(args.serial))
    folder, current, id_count = dump(device, args.label, args.output_dir)

    print(f"Dump saved: {folder}")
    print(f"  package:  {current.get('package')}")
    print(f"  activity: {current.get('activity')}")
    print(f"  unique resource-ids: {id_count}")

    if current.get("package") != FIVERR_PACKAGE:
        print(f"[WARN] Current package is '{current.get('package')}', not '{FIVERR_PACKAGE}'. "
              "Dump still saved, but you may have captured the wrong app.", file=sys.stderr)


if __name__ == "__main__":
    main()
