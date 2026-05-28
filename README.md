# Fiverr Automation

Automates two things for the Fiverr Android app:

1. **Keeps your account online.** A long-running loop performs gentle human-like activity (small scrolls, tab switches, pull-to-refresh) on a fixed schedule so the phone doesn't sleep, the ADB session stays warm, and Fiverr keeps showing you as "Online."
2. **Auto-replies to first-time contacts with a configured message.** Detects rows in your Inbox where someone has messaged you for the first time (Fiverr renders a stopwatch icon next to their name) and posts your reply (default: "Hello"). Keeps your response-rate metric high.

The configured message can be edited in `config.json` without touching any code.

> **Disclaimer.** Automating interactions with the Fiverr app may violate Fiverr's Terms of Service. Use at your own risk. Your account may be suspended. The author takes no responsibility. See `NOTICE.md`.

## What you need

- **Windows** (the `.bat` launchers assume Windows; the Python scripts themselves are cross-platform).
- **Python 3.8 or later.** Download: https://www.python.org/downloads/ — make sure "Add Python to PATH" is checked during install.
- **Android Platform Tools (`adb`).** Download: https://developer.android.com/studio/releases/platform-tools — unzip somewhere and add the folder to your PATH.
- **An Android device or emulator** with:
  - The **Fiverr app** installed and signed into your account.
  - **USB debugging** (or wireless ADB) enabled. For Android phones: Settings → About → tap Build number 7 times → back → Developer options → enable USB debugging. For emulators (e.g. MuMu, BlueStacks), ADB is usually exposed on a local IP:PORT — check your emulator's docs.

## First-time setup

1. **Clone or download** this repo to any folder on your PC.
2. **Open a terminal in that folder** (Shift + Right-click → "Open PowerShell window here").
3. **Run `setup.bat`.** It installs the Python dependencies and runs the preflight checks. You'll get a summary of what's OK and what's missing.
4. **Plug in your phone** (USB) or connect via wireless ADB. Confirm with `adb devices` — you should see your device listed.
5. **Edit `config.json`** (any text editor — Notepad is fine). Set:
   - `serial` — your device's ADB serial or `"IP:PORT"` for wireless. Leave as `null` to auto-detect a single connected device.
   - `message` — the reply text. Default `"Hello"`.
   - `send` — leave as `false` to dry-run first (recommended). Set to `true` when ready to actually post replies.
6. **Run `check.bat`** to verify everything is green.
7. **Run `dry-run.bat`** to see what the script would do without sending. Open Fiverr to the Inbox first.
8. When the dry-run looks right, set `"send": true` in `config.json` and **run `start.bat`**. Leave it running. `Ctrl+C` to stop.

## Configuration

`config.json` (lives next to the scripts):

```json
{
  "serial": null,
  "message": "Hello",
  "send": false,
  "min_interval_seconds": 60.0,
  "max_interval_seconds": 180.0,
  "max_replies_per_scan": 5
}
```

| Field | Meaning |
|---|---|
| `serial` | ADB serial or `"IP:PORT"` (wireless). `null` = auto-detect a single attached device. |
| `message` | The reply text sent to brand-new contacts. |
| `send` | `false` = dry-run (no messages sent). `true` = live. **Always dry-run first.** |
| `min_interval_seconds` | Lower bound for the random delay between actions. |
| `max_interval_seconds` | Upper bound. The actual delay is uniform-random in this range. |
| `max_replies_per_scan` | Cap on replies posted per Inbox visit. Prevents a flood if many new messages arrive at once. |

Per-sender history is kept in `replied_senders.json` (auto-created). The same sender is never re-replied, even if you reset Fiverr's read state.

## The launchers

All of these read `config.json` and can be double-clicked:

| BAT file | What it does |
|---|---|
| `setup.bat` | One-time: installs Python deps + runs preflight. |
| `check.bat` | Re-runs preflight checks only. Good for troubleshooting. |
| `dry-run.bat` | Runs the watch loop in dry-run mode regardless of `config.send`. Safe — sends nothing. |
| `start.bat` | Runs the watch loop using `config.send` (sends if true, dry-runs if false). |
| `dump-ui.bat` | Prompts for a label and saves a screenshot + UI XML of the current screen into `dumps/`. Diagnostic only. |

You can also run any script directly: `python watch_and_reply.py [--send] [--message "..."]`. CLI flags override `config.json`.

## How it works (brief)

The loop, each iteration:

1. Sleeps a random interval inside `[min_interval_seconds, max_interval_seconds]`.
2. Performs one randomly-chosen safe gesture:
   - **wake-key** — `KEYCODE_WAKEUP`. Always a no-op for app state.
   - **bounce-scroll** — small swipe up + matching swipe down. Nets ~zero scroll.
   - **switch-tab** — taps one of the 4 bottom-nav tabs.
   - **pull-refresh** — if the current screen has a swipe-to-refresh container, drag down inside it.
3. If we end up on the **Inbox** after the gesture, scan for first-time-contact rows. For each one not already in `replied_senders.json`, open the conversation, type the configured message, tap Send, back out, record the sender.

First-time-contact detection uses Fiverr's initial-placeholder avatar (`avatar_txt_vw` resource-id) as a proxy for "this user hasn't uploaded a profile picture" — strongly correlated with first-time contacts in practice. The history file is the authoritative "already replied" signal.

## Troubleshooting

**`adb` not found.** Install Android Platform Tools and add the folder to your PATH. Restart your terminal.

**`adb devices` shows nothing.** USB debugging not enabled, or wireless ADB not connected. For wireless: `adb connect <ip>:5555`. Confirm with `adb devices`.

**Preflight says "uiautomator2 agent connect failed."** First-time setup on this device may need: `python -m uiautomator2 init` to install the on-device agent.

**Script says foreground isn't Fiverr.** Open the Fiverr app on the phone before starting. The script won't fight to bring it forward.

**Replies aren't sending.** Confirm `"send": true` in `config.json` (and that you saved the file). Run `check.bat` to verify. Check `replied_senders.json` — if the sender's name is there, they were already replied to and will be skipped.

**A real contact got "Hello" by mistake.** The detection uses "user has no profile picture" as a proxy. In practice this catches new contacts almost exclusively, but a real contact with no avatar would also trigger. Add their name to `replied_senders.json` manually (any timestamp) to skip them going forward.

**Connection drops mid-run.** uiautomator2 sometimes loses its on-device agent connection. The watch loop reconnects automatically on the next cycle. If it keeps failing, restart the script.

## File reference

```
.
├── README.md              this file
├── NOTICE.md              copyright + disclaimer
├── CLAUDE.md              guidance for AI coding agents
├── .gitignore
├── requirements.txt
├── config.json            EDIT THIS
├── setup.bat              first-time setup
├── check.bat              preflight only
├── dry-run.bat            safe test
├── start.bat              live
├── dump-ui.bat            diagnostic
├── config_util.py         shared config loader
├── preflight.py           startup checks
├── dump_ui.py             diagnostic UI dumper
├── keepalive.py           keepalive-only loop (no auto-reply)
├── auto_reply.py          one-shot auto-reply scan
└── watch_and_reply.py     main looping script (combines keepalive + reply)
```

Files that exist only at runtime (gitignored):

```
dumps/                     diagnostic output of dump_ui.py
replied_senders.json       per-sender reply history
```

## License

See `NOTICE.md` — all rights reserved.
