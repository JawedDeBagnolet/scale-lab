#!/usr/bin/env python3
"""Patch telegram_bot.py: add sync notify_backend_group_sync() and call it."""

from pathlib import Path

BOT_FILE = Path("/root/telegram_bot.py")
src = BOT_FILE.read_text()

if "notify_backend_group_sync" in src:
    print("Already patched — skipping")
    exit(0)

# ── 1. Insert sync function before TELEGRAM API HELPERS ──
SYNC_FN = '''
def notify_backend_group_sync(chat_id, chat_title):
    """Synchronous — tell backend about a new pending group."""
    import urllib.request
    import json as _json
    try:
        data = _json.dumps({"chat_id": chat_id, "chat_title": chat_title}).encode()
        req = urllib.request.Request(
            BACKEND_URL + "/api/telegram/bot/group_added",
            data=data,
            headers={"Content-Type": "application/json", "X-Scale-Token": API_SECRET},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = _json.loads(resp.read())
            print("[GROUP] Backend notified for chat %s: %s" % (chat_id, result))
    except Exception as e:
        print("[GROUP] Backend notify failed for chat %s: %s" % (chat_id, e))


'''

marker = "# ============ TELEGRAM API HELPERS ============"
if marker not in src:
    print("ERROR: could not find TELEGRAM API HELPERS marker")
    exit(1)

patched = src.replace(marker, SYNC_FN + marker, 1)
print("Patch 1: inserted notify_backend_group_sync() function")

# ── 2. Insert call after save_data("pending_groups.json", pending) ──
# Find the first occurrence (in my_chat_member handler)
save_line = 'save_data("pending_groups.json", pending)'
idx = patched.find(save_line)
if idx == -1:
    print("ERROR: could not find save_data pending_groups line")
    exit(1)

eol = patched.index("\n", idx)
# Get indentation of the save_data line
line_start = patched.rfind("\n", 0, idx) + 1
indent = ""
for ch in patched[line_start:]:
    if ch in (" ", "\t"):
        indent += ch
    else:
        break

call = f'\n{indent}notify_backend_group_sync(chat_id, chat.get("title", ""))'
patched = patched[:eol] + call + patched[eol:]
print("Patch 2: added notify_backend_group_sync() call after save_data")

# ── 3. Remove old async notify_backend_group if present ──
if "async def notify_backend_group(" in patched:
    # Remove the async function (it doesn't work in sync context)
    start = patched.find("# ── Notify backend when bot is added to a group ──")
    if start == -1:
        start = patched.find("async def notify_backend_group(")
    if start != -1:
        # Find the end of the function (next def or next blank line after the function)
        end = patched.find("\ndef ", start + 10)
        if end == -1:
            end = patched.find("\n\n\n", start + 10)
        if end != -1:
            patched = patched[:start] + patched[end:]
            print("Patch 3: removed old async notify_backend_group()")

# Also remove any old asyncio.ensure_future call
if "asyncio.ensure_future(notify_backend_group(" in patched:
    patched = patched.replace(
        "import asyncio; asyncio.ensure_future(notify_backend_group(chat_id, chat.get(\"title\", \"\")))",
        ""
    )
    print("Patch 4: removed old asyncio.ensure_future call")

BOT_FILE.write_text(patched)
print("\nDone — restart with: systemctl restart telegram-bot")
