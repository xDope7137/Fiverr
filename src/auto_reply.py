"""Auto-reply to first-time contacts in the Fiverr inbox.

A "new contact" is detected when an inbox row contains a descendant with
resource-id `avatar_txt_vw` — the initial-placeholder TextView Fiverr
renders when the sender hasn't uploaded a profile picture. That signal
strongly correlates with first-time contacts in practice.

Each successfully-replied sender is recorded in `replied_senders.json` in
the project root. The same sender will never be replied to twice across runs.

Default mode is DRY-RUN — it walks the inbox, identifies who it WOULD reply
to, and logs each step without typing or tapping send. Pass `--send` to
actually post replies.

Configuration is read from `config.json` in the project root:
  - serial   : ADB serial / IP:PORT (null = auto-detect single device)
  - message  : the reply text (default "Hello")
  - send     : false = dry-run; true = actually post replies

CLI flags override the config file.

Usage:
    # safe — uses config; if send=false, just shows who would get a reply
    python auto_reply.py

    # for real — overrides config and sends
    python auto_reply.py --send

    # customize and cap per run
    python auto_reply.py --send --message "Hi!" --limit 3
"""
import argparse
import json
import os
import random
import sys
import time
from datetime import datetime

import uiautomator2 as u2

from config_util import load_config, resolve_serial

FIVERR_PACKAGE = "com.fiverr.fiverr"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
HISTORY_PATH = os.path.join(PROJECT_ROOT, "replied_senders.json")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_history():
    if not os.path.exists(HISTORY_PATH):
        return {}
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log(f"warn: history file unreadable ({e}); starting fresh")
        return {}


def save_history(history):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def connect(serial):
    try:
        return u2.connect(serial)
    except Exception as e:
        print(f"[ERROR] connect failed: {e}", file=sys.stderr)
        print("[HINT] Run `adb connect <ip>:5555` first; check `adb devices`.", file=sys.stderr)
        sys.exit(1)


def ensure_inbox(d):
    cur = d.app_current()
    if cur.get("package") != FIVERR_PACKAGE:
        log(f"[ERROR] foreground is {cur.get('package')!r}, not Fiverr — open Fiverr first")
        sys.exit(1)
    # Back out of any deeper screen until we're on MainActivity.
    for _ in range(3):
        activity = d.app_current().get("activity", "")
        if "MainActivity" in activity:
            break
        log(f"  pressing back to leave {activity!r}")
        d.press("back")
        time.sleep(1.5)
    # Tap the inbox tab (no-op if already there).
    btn = d(resourceId=f"{FIVERR_PACKAGE}:id/inbox")
    if btn.exists:
        btn.click()
        time.sleep(random.uniform(2.0, 3.0))


def find_new_contact_names(d):
    """Return display-name strings for every visible inbox row whose avatar
    slot is a placeholder (`avatar_txt_vw` present) — i.e. likely first-time
    contacts.

    Matches placeholder y-center against inbox_display_name y-center within
    the same row (rows are ~190px tall, so a 60px tolerance is comfortably
    safe).
    """
    placeholders = d(resourceId=f"{FIVERR_PACKAGE}:id/avatar_txt_vw")
    names = d(resourceId=f"{FIVERR_PACKAGE}:id/inbox_display_name")

    name_centers = []
    for i in range(names.count):
        info = names[i].info
        b = info.get("bounds")
        text = (info.get("text") or "").strip()
        if not b or not text:
            continue
        name_centers.append(((b["top"] + b["bottom"]) // 2, text))

    new_contacts = []
    for j in range(placeholders.count):
        b = placeholders[j].info.get("bounds")
        if not b:
            continue
        ph_y = (b["top"] + b["bottom"]) // 2
        for yc, text in name_centers:
            if abs(yc - ph_y) < 60:
                if text not in new_contacts:
                    new_contacts.append(text)
                break
    return new_contacts


def open_and_reply(d, display_name, message, dry_run):
    """Open the conversation for `display_name`, type the message, send, back
    out. Returns True iff we actually sent (False on dry-run or any failure)."""
    row = d(resourceId=f"{FIVERR_PACKAGE}:id/inbox_display_name", text=display_name)
    if not row.exists:
        log(f"  warn: row for {display_name!r} disappeared — skipping")
        return False
    row.click()
    time.sleep(random.uniform(2.5, 4.0))

    activity = d.app_current().get("activity", "")
    if "Conversation" not in activity:
        log(f"  warn: did not land on ConversationActivity (got {activity!r}) — backing out")
        d.press("back")
        time.sleep(1.5)
        return False

    composer = d(resourceId=f"{FIVERR_PACKAGE}:id/conversation_composer_edit_text")
    send_btn = d(resourceId=f"{FIVERR_PACKAGE}:id/conversation_composer_send_btn")

    if not composer.exists:
        log(f"  warn: compose field not found — backing out")
        d.press("back")
        time.sleep(1.5)
        return False

    if dry_run:
        log(f"  [DRY-RUN] would type {message!r} and tap send")
        time.sleep(random.uniform(1.0, 2.0))
        d.press("back")
        time.sleep(random.uniform(1.0, 1.8))
        return False

    composer.click()
    time.sleep(random.uniform(0.4, 0.9))
    composer.send_keys(message)
    time.sleep(random.uniform(0.6, 1.4))

    # Verify the type actually landed in the field before we send.
    # NB: on this Android build an empty EditText returns the hint string
    # ("Type a message…") from .info["text"], so we check that our message
    # is IN the field — that distinguishes "typed successfully" from "empty
    # field showing hint" reliably.
    typed = (composer.info.get("text") or "")
    if message not in typed:
        log(f"  warn: type did not land (field shows {typed!r}) — backing out without sending")
        d.press("back")
        time.sleep(1.5)
        return False

    if not send_btn.exists:
        log(f"  warn: send button missing — backing out")
        d.press("back")
        time.sleep(1.5)
        return False
    send_btn.click()
    time.sleep(random.uniform(1.8, 3.0))

    log(f"  sent {message!r} to {display_name!r}")
    d.press("back")
    time.sleep(random.uniform(1.0, 1.8))
    return True


def run(serial, message, dry_run, limit):
    d = connect(serial)
    ensure_inbox(d)

    history = load_history()
    candidates = find_new_contact_names(d)
    log(f"new-contact rows visible: {candidates}")

    if not candidates:
        log("nothing to do.")
        return

    sent_count = 0
    for name in candidates:
        if limit is not None and sent_count >= limit:
            log(f"hit --limit {limit}; stopping")
            break
        if name in history:
            log(f"  skipping {name!r} — already replied at {history[name].get('ts')}")
            continue
        log(f"processing {name!r}")
        ok = open_and_reply(d, name, message, dry_run)
        if ok:
            history[name] = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "message": message,
            }
            save_history(history)
            sent_count += 1
            time.sleep(random.uniform(3.0, 6.0))

    log(f"done. dry_run={dry_run}. replied to {sent_count} new contact(s).")


def main():
    p = argparse.ArgumentParser(description="Auto-reply to first-time contacts in the Fiverr inbox. Reads config.json; CLI flags override.")
    p.add_argument("--serial", default=None, help="Override serial / IP:PORT from config.")
    p.add_argument("--message", default=None, help="Override reply text from config.")
    p.add_argument("--send", action="store_true", help="Actually send (overrides config).")
    p.add_argument("--dry-run", action="store_true", help="Force dry-run (overrides config).")
    p.add_argument("--limit", type=int, default=None, help="Max replies per run. Default: unlimited.")
    args = p.parse_args()

    cfg = load_config()
    serial = resolve_serial(args.serial)
    message = args.message if args.message is not None else cfg["message"]
    send = cfg["send"]
    if args.send:
        send = True
    if args.dry_run:
        send = False

    try:
        run(serial, message, dry_run=not send, limit=args.limit)
    except KeyboardInterrupt:
        log("interrupted by user")


if __name__ == "__main__":
    main()
