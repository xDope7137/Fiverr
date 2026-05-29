# Fiverr Automation — Claude guide

Fiverr Android-app texting automation. Drives `com.fiverr.fiverr` via uiautomator2 + ADB.

## Layout

```
fiverr-automation/         <- project root: config + BAT launchers + docs
├── config.json            user-editable settings
├── *.bat                  Windows launchers (setup/check/dry-run/start/dump-ui)
├── README.md              end-user docs
├── CLAUDE.md              this file (agent-facing)
├── NOTICE.md              copyright + disclaimer
└── src/                   all Python lives here
    ├── config_util.py     shared `config.json` loader (CONFIG_PATH resolves up one level)
    ├── preflight.py       startup checks (Python, adb, uiautomator2, device, Fiverr, agent)
    ├── dump_ui.py         diagnostic: screenshot + XML + resource-ids of the current screen
    ├── keepalive.py       keepalive-only loop (no replies)
    ├── auto_reply.py      one-shot inbox scan + reply; exports helpers re-used by watch_and_reply
    └── watch_and_reply.py main loop: keepalive gestures + opportunistic inbox auto-reply
```

Runtime data lives at the project root and is gitignored:

```
dumps/                     dump_ui.py output (real screenshots — never commit)
replied_senders.json       per-sender reply history (PII — never commit)
```

End-user docs live in `README.md`. This file is for AI agents / contributors.

## Non-obvious gotchas

- **Splash vs main activity:** the Fiverr launcher activity is `.activityandfragments.entrypoints.FVREntryPoint`; the actual tabs (inbox/home/orders/account) live in `.ui.activity.MainActivity`. Allow ~10s after launch before dumping or `resource-id` lists will be mostly empty.
- **`dump_ui.py` does NOT call `app_start`.** That's deliberate so deep screens (open conversation, compose) can be inspected without losing state. Navigate manually first, then run the dumper.
- **`keepalive.py` actions are deliberately constrained to a safe set:** WAKEUP key, tiny bounce-scroll, bottom-nav tab switch (home / inbox / orders / account), and pull-to-refresh on screens whose XML contains a `*swipe_to_refresh*` resource-id. It must NEVER open a conversation, type, press BACK/HOME/MENU, or tap arbitrary elements — those would risk side effects (sending half-typed text, drafting messages, dismissing dialogs). New actions added to keepalive must stay within this rule.
- **`auto_reply.py` / `watch_and_reply.py` default to DRY-RUN.** Without `--send` (or `"send": true` in config) they walk the flow and log what they would do but don't type or tap send. Always dry-run first after any change.
- **"New contact" detection signal:** any inbox row whose `avatar_view_layout` contains a child with `resource-id="...:id/avatar_txt_vw"` (Fiverr's initial-letter placeholder rendered when the sender has no profile picture). This is a proxy — the literal stopwatch icon Fiverr draws on first-time rows is a compound drawable on `inbox_display_name` and is not exposed in `dump_hierarchy()` (confirmed by diffing compressed vs uncompressed dumps). For Fiverr's user demographics the proxy is reliable in practice; combine with the local history DB for full safety.
- **The proxy persists after you reply.** Confirmed empirically: after sending the auto-reply, the inbox row's stopwatch icon becomes the regular moon icon (Fiverr considers the response-rate obligation met), but `avatar_txt_vw` is still there because the sender's avatar is still unset. Conclusion: **`replied_senders.json` is the authoritative skip signal, not the XML.** Never wipe that file casually.
- **EditText hint quirk.** `d(resourceId='...conversation_composer_edit_text').info['text']` returns the hint string `"Type a message…"` when the field is empty, NOT an empty string. Don't use "field is empty after send" as a success check — instead, verify BEFORE tapping send that `message in composer.info['text']` (i.e. typing landed). That's what `auto_reply.py:open_and_reply` does.
- **Multi-display emulators (e.g. MuMu).** The Fiverr nodes have `display-id="2"` but `device.screenshot()` defaults to display 0 and returns the launcher. For a real Fiverr screenshot use `adb shell screencap -d 2 -p /sdcard/x.png && adb pull /sdcard/x.png`.
- `dumps/` and `replied_senders.json` are gitignored — they contain real account data and must never be committed.

## Known good selectors

- Bottom nav: `com.fiverr.fiverr:id/{home,inbox,orders,account}`
- Inbox list: `inbox_recycler_view`; row fields `inbox_display_name`, `inbox_date`, `inbox_message_text`
- Pull-to-refresh containers: matched by `resource-id` regex `.*swipe_to_refresh.*` (so far seen: `inbox_swipe_to_refresh`; other tabs use similarly-named ids).
- Conversation screen (`.activityandfragments.conversations.ConversationActivity`): `conversation_recycler_view` (message list), `conversation_composer_edit_text` (input), `conversation_composer_send_btn` (send), `conversation_composer_attach_btn`, `conversation_composer_create_an_offer_button`, `conversation_composer_quick_response_btn`, `main_toolbar` (header with sender name + last-seen), `mutual_orders` (shown when seller and buyer have prior order history — absent for first-time contacts).
- New-contact-row proxy: per-row descendant `com.fiverr.fiverr:id/avatar_txt_vw` (TextView with sender's initial, rendered when no profile pic is set).
- Inbox toolbar filter button: `action_filter`

When adding new selectors here, append to the list — Fiverr resource-ids may churn across app versions; keep old candidates around for fallback.

## Roadmap

1. Image-based stopwatch detection (crop the row's icon region from a display-2 screenshot, classify clock-vs-moon by color) — would let us avoid the `avatar_txt_vw` proxy entirely.
2. Inbox-list scrolling so scans see more than the first ~6 visible rows.
3. A `DeviceFacade` class wrapping `uiautomator2` so per-script `connect()` boilerplate goes away.
4. Multi-template replies (rotate between a small set so the bot doesn't look templated).
5. SQLite for history (current JSON file is fine but won't scale to thousands of senders).
