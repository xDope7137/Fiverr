"""watch_and_reply.py — Human-like keepalive loop that also auto-replies to
brand-new Fiverr inbox contacts.

Each iteration:
  1. Sleep a random interval (jittered).
  2. Perform one safe gesture: wake-key, bounce-scroll, switch-tab
     (home/inbox/orders/account), or pull-refresh.
  3. If the gesture left us on the Inbox page (Fiverr MainActivity with
     `inbox_recycler_view` visible), scan for first-time-contact rows
     (rows containing an `avatar_txt_vw` placeholder). For each such
     contact not already in `replied_senders.json`, open the conversation,
     type the configured message, tap Send, back out, record the sender.

The configurable message lives in `config.json` next to this script (auto-
created with safe defaults on first run). Edit that file to change what
gets sent without touching the code. CLI flags override the file.

Default is DRY-RUN. Set `"send": true` in the config (or pass `--send`) to
actually post replies.

Usage:
    python watch_and_reply.py
    python watch_and_reply.py --send
    python watch_and_reply.py --send --message "Hi!"
"""
import argparse
import os
import random
import sys
import time
from datetime import datetime

import uiautomator2 as u2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from auto_reply import (  # noqa: E402
    find_new_contact_names,
    open_and_reply,
    load_history,
    save_history,
)
from config_util import CONFIG_PATH, load_config  # noqa: E402

FIVERR_PACKAGE = "com.fiverr.fiverr"
TABS = ["home", "inbox", "orders", "account"]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# --- Safe gestures (mirrors keepalive.py) ---

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
    return "bounce-scroll"


def switch_tab(d):
    tab = random.choice(TABS)
    btn = d(resourceId=f"{FIVERR_PACKAGE}:id/{tab}")
    if not btn.exists:
        return f"switch-tab '{tab}' not on screen — skipped"
    btn.click()
    time.sleep(random.uniform(1.5, 3.0))
    return f"switch-tab -> {tab}"


def pull_refresh(d):
    r = d(resourceIdMatches=r".*swipe_to_refresh.*")
    if not r.exists:
        return None
    b = r.info.get("bounds")
    if not b:
        return None
    cx = (b["left"] + b["right"]) // 2 + random.randint(-30, 30)
    y0 = b["top"] + random.randint(40, 100)
    pull = random.randint(450, 650)
    d.swipe(cx, y0, cx, y0 + pull, duration=random.uniform(0.35, 0.55))
    time.sleep(random.uniform(1.5, 3.0))
    return "pull-refresh"


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
    for fn, w in ACTIONS:
        cum += w
        if r < cum:
            return fn
    return ACTIONS[-1][0]


# --- Inbox scan ---

def is_on_inbox(d):
    cur = d.app_current()
    if cur.get("package") != FIVERR_PACKAGE:
        return False
    if "MainActivity" not in cur.get("activity", ""):
        return False
    return d(resourceId=f"{FIVERR_PACKAGE}:id/inbox_recycler_view").exists


def scan_inbox(d, message, send, max_replies):
    history = load_history()
    candidates = find_new_contact_names(d)
    if not candidates:
        log("  scan: no new-contact rows visible")
        return 0
    log(f"  scan: candidates {candidates}")
    sent = 0
    for name in candidates:
        if sent >= max_replies:
            log(f"  hit max_replies_per_scan ({max_replies}); rest will be picked up next scan")
            break
        if name in history:
            log(f"    skip {name!r} — already replied at {history[name].get('ts')}")
            continue
        log(f"    processing {name!r}")
        ok = open_and_reply(d, name, message, dry_run=not send)
        if ok:
            history[name] = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "message": message,
            }
            save_history(history)
            sent += 1
            time.sleep(random.uniform(3.0, 6.0))
    return sent


# --- Main loop ---

def connect(serial):
    try:
        return u2.connect(serial)
    except Exception as e:
        print(f"[ERROR] connect failed: {e}", file=sys.stderr)
        print("[HINT] Run `adb connect <ip>:5555` first; check `adb devices`.", file=sys.stderr)
        sys.exit(1)


def run(cfg):
    d = connect(cfg["serial"])
    try:
        d.shell("svc power stayon true")
        log("svc power stayon=true (screen will stay on while plugged in)")
    except Exception as e:
        log(f"warn: could not set stayon: {e}")

    log("watch_and_reply started")
    log(f"  serial={cfg['serial']!r}")
    log(f"  interval={cfg['min_interval_seconds']:.0f}-{cfg['max_interval_seconds']:.0f}s")
    log(f"  message={cfg['message']!r}  send={cfg['send']}  max_replies_per_scan={cfg['max_replies_per_scan']}")
    log(f"  config file: {CONFIG_PATH} (edit to change defaults)")
    log("Ctrl+C to stop.")

    iteration = 0
    while True:
        iteration += 1
        wait = random.uniform(cfg["min_interval_seconds"], cfg["max_interval_seconds"])
        log(f"#{iteration} sleep {wait:.1f}s")
        time.sleep(wait)

        # Reconnect-tolerant current-screen check.
        try:
            cur = d.app_current()
        except Exception as e:
            log(f"warn: app_current failed ({e}); reconnecting")
            try:
                d = u2.connect(cfg["serial"])
                cur = d.app_current()
            except Exception as e2:
                log(f"error: reconnect failed ({e2}); will retry next cycle")
                continue

        if cur.get("package") != FIVERR_PACKAGE:
            log(f"#{iteration} foreground={cur.get('package')} (not Fiverr); leaving alone")
            continue

        # Step 1: act human.
        fn = pick_action()
        try:
            label = fn(d)
            log(f"#{iteration} action: {label}")
        except Exception as e:
            log(f"#{iteration} action failed: {e}")
            continue

        # Step 2: if we ended up on the Inbox, scan for the stopwatch.
        try:
            if is_on_inbox(d):
                log(f"#{iteration} on inbox — scanning")
                replied = scan_inbox(
                    d, cfg["message"], cfg["send"], cfg["max_replies_per_scan"]
                )
                if replied:
                    log(f"#{iteration} replied to {replied} new contact(s) this scan")
        except Exception as e:
            log(f"#{iteration} scan failed: {e}")


def main():
    p = argparse.ArgumentParser(description="Human-like keepalive loop + auto-reply to first-time Fiverr contacts. CLI flags override config.json.")
    p.add_argument("--serial", default=None, help="Override serial / IP:PORT from config.")
    p.add_argument("--message", default=None, help="Override reply message from config.")
    p.add_argument("--min-interval", type=float, default=None, help="Override min seconds between actions.")
    p.add_argument("--max-interval", type=float, default=None, help="Override max seconds between actions.")
    p.add_argument("--max-replies-per-scan", type=int, default=None, help="Override max replies per inbox scan.")
    p.add_argument("--send", action="store_true", help="Actually send replies (overrides config).")
    p.add_argument("--dry-run", action="store_true", help="Force dry-run (overrides config).")
    args = p.parse_args()

    cfg = load_config()
    if args.serial is not None:
        cfg["serial"] = args.serial
    if args.message is not None:
        cfg["message"] = args.message
    if args.min_interval is not None:
        cfg["min_interval_seconds"] = args.min_interval
    if args.max_interval is not None:
        cfg["max_interval_seconds"] = args.max_interval
    if args.max_replies_per_scan is not None:
        cfg["max_replies_per_scan"] = args.max_replies_per_scan
    if args.send:
        cfg["send"] = True
    if args.dry_run:
        cfg["send"] = False

    if cfg["min_interval_seconds"] > cfg["max_interval_seconds"]:
        print("[ERROR] min_interval > max_interval", file=sys.stderr)
        sys.exit(2)

    try:
        run(cfg)
    except KeyboardInterrupt:
        log("interrupted by user")


if __name__ == "__main__":
    main()
