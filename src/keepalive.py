"""Keepalive: gentle human-like activity so the phone stays awake, the ADB
session stays warm, and Fiverr keeps showing the account as online.

Each iteration sleeps a random interval, then performs one randomly-chosen
SAFE action:

  - wake-key      : KEYCODE_WAKEUP. Always a no-op for app state.
  - bounce-scroll : tiny up+down swipe in the middle of the screen; nets to
                    ~zero scroll. Designed too small to trigger pull-refresh.
  - switch-tab    : taps a random bottom-nav tab (home/inbox/orders/account).
                    Tapping the current tab is a no-op; switching tabs just
                    changes pages, never opens a conversation.
  - pull-refresh  : drags down from the top of the current screen's
                    swipe-to-refresh container (if one exists). Falls back to
                    bounce-scroll on screens that don't support refresh.

The script never opens a conversation, never types, never presses
BACK/HOME/MENU. It will warn (but not interfere) if Fiverr is not the
foreground app.

Reads `serial` from `config.json`; CLI flags override.

Usage:
    python keepalive.py [--serial IP:PORT] [--min-interval 60] [--max-interval 180]
                        [--package com.fiverr.fiverr]
"""
import argparse
import random
import sys
import time
from datetime import datetime

import uiautomator2 as u2

from config_util import resolve_serial

FIVERR_PACKAGE = "com.fiverr.fiverr"
TABS = ["home", "inbox", "orders", "account"]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def wake_key(d):
    d.press("wakeup")
    return "wake-key"


def bounce_scroll(d):
    w, h = d.window_size()
    cx = w // 2 + random.randint(-25, 25)
    y_high = int(h * (0.55 + random.uniform(-0.04, 0.04)))
    y_low = int(h * (0.42 + random.uniform(-0.03, 0.03)))
    d.swipe(cx, y_high, cx, y_low, duration=random.uniform(0.25, 0.45))
    time.sleep(random.uniform(0.4, 1.1))
    d.swipe(cx, y_low, cx, y_high, duration=random.uniform(0.25, 0.45))
    return f"bounce-scroll x={cx} y={y_high}->{y_low}"


def switch_tab(d):
    tab = random.choice(TABS)
    btn = d(resourceId=f"{FIVERR_PACKAGE}:id/{tab}")
    if not btn.exists:
        return f"switch-tab '{tab}' not found (off main screen?) — skipped"
    btn.click()
    time.sleep(random.uniform(1.5, 3.0))
    return f"switch-tab -> {tab}"


def pull_refresh(d):
    refresh = d(resourceIdMatches=r".*swipe_to_refresh.*")
    if not refresh.exists:
        return None
    bounds = refresh.info.get("bounds")
    if not bounds:
        return None
    cx = (bounds["left"] + bounds["right"]) // 2 + random.randint(-30, 30)
    y_start = bounds["top"] + random.randint(40, 100)
    pull = random.randint(450, 650)
    d.swipe(cx, y_start, cx, y_start + pull, duration=random.uniform(0.35, 0.55))
    time.sleep(random.uniform(1.5, 3.0))
    return f"pull-refresh y={y_start}->{y_start + pull}"


def pull_refresh_or_bounce(d):
    r = pull_refresh(d)
    if r is not None:
        return r
    return bounce_scroll(d) + " (no-refresh-fallback)"


ACTIONS = [
    (wake_key, 0.10),
    (bounce_scroll, 0.25),
    (switch_tab, 0.45),
    (pull_refresh_or_bounce, 0.20),
]


def pick_action():
    r = random.random()
    cum = 0.0
    for fn, weight in ACTIONS:
        cum += weight
        if r < cum:
            return fn
    return ACTIONS[-1][0]


def connect(serial):
    try:
        return u2.connect(serial)
    except Exception as e:
        print(f"[ERROR] connect failed: {e}", file=sys.stderr)
        print("[HINT] Run `adb connect <ip>:5555` first, or check `adb devices`.", file=sys.stderr)
        sys.exit(1)


def keepalive(serial, min_int, max_int, package):
    d = connect(serial)

    try:
        d.shell("svc power stayon true")
        log("svc power stayon=true (screen will stay on while plugged in)")
    except Exception as e:
        log(f"warn: could not set stayon: {e}")

    log(f"keepalive started: interval {min_int:.0f}-{max_int:.0f}s, target {package}")
    log("Ctrl+C to stop.")
    iteration = 0
    while True:
        iteration += 1
        wait = random.uniform(min_int, max_int)
        log(f"#{iteration} sleep {wait:.1f}s")
        time.sleep(wait)

        try:
            cur = d.app_current()
        except Exception as e:
            log(f"warn: app_current failed ({e}); reconnecting")
            try:
                d = u2.connect(serial)
                cur = d.app_current()
            except Exception as e2:
                log(f"error: reconnect failed ({e2}); will retry next cycle")
                continue

        if cur.get("package") != package:
            log(f"note: foreground={cur.get('package')} (expected {package}); leaving it alone")

        fn = pick_action()
        try:
            label = fn(d)
            log(f"#{iteration} action: {label}")
        except Exception as e:
            log(f"#{iteration} action failed: {e}")


def main():
    p = argparse.ArgumentParser(description="Keep the phone awake and Fiverr session alive with gentle human-like activity (tab navigation, bounce-scrolls, pull-to-refresh).")
    p.add_argument("--serial", default=None,
                   help="Override serial / IP:PORT from config.json.")
    p.add_argument("--min-interval", type=float, default=60.0,
                   help="Minimum seconds between actions. Default 60.")
    p.add_argument("--max-interval", type=float, default=180.0,
                   help="Maximum seconds between actions. Default 180.")
    p.add_argument("--package", default=FIVERR_PACKAGE,
                   help=f"Target package (warning only). Default {FIVERR_PACKAGE}.")
    args = p.parse_args()

    if args.min_interval <= 0 or args.max_interval <= 0:
        print("[ERROR] intervals must be positive", file=sys.stderr)
        sys.exit(2)
    if args.min_interval > args.max_interval:
        print("[ERROR] --min-interval must be <= --max-interval", file=sys.stderr)
        sys.exit(2)

    try:
        keepalive(resolve_serial(args.serial), args.min_interval, args.max_interval, args.package)
    except KeyboardInterrupt:
        log("interrupted by user")


if __name__ == "__main__":
    main()
