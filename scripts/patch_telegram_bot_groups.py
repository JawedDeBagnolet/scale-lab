#!/usr/bin/env python3
"""Patch telegram_bot.py on VPS to notify backend when bot is added to a group.

The bot already handles my_chat_member and saves to pending_groups.json.
This patch adds a notify_backend_group() call so the backend DB stays in sync.
"""

import re
import sys
import shutil
from pathlib import Path

BOT_FILE = Path("/root/telegram_bot.py")

def main():
    if not BOT_FILE.exists():
        print(f"ERROR: {BOT_FILE} not found")
        sys.exit(1)

    src = BOT_FILE.read_text()
    backup = BOT_FILE.with_suffix(".py.bak_groups")
    shutil.copy2(BOT_FILE, backup)
    print(f"Backup: {backup}")

    patched = src
    applied = 0

    # ── Patch 1: Add notify_backend_group() function ──
    # Insert after the existing notify_backend() function (for /start)
    # Look for the BACKEND_API constant or the notify_backend function
    if "notify_backend_group" not in patched:
        # Find a good insertion point — after BACKEND_API or notify_backend
        marker = 'BACKEND_API = '
        idx = patched.find(marker)
        if idx == -1:
            # Try finding it after imports
            marker = 'import json'
            idx = patched.find(marker)

        if idx != -1:
            # Find end of that line
            eol = patched.index('\n', idx)
            insert_pos = eol + 1

            fn_code = '''
# ── Notify backend when bot is added to a group ──
async def notify_backend_group(chat_id, chat_title):
    """Tell the backend about a new pending group."""
    try:
        data = {"chat_id": chat_id, "chat_title": chat_title}
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{BACKEND_API}/telegram/bot/group_added",
                json=data,
                headers={"X-Scale-Token": API_TOKEN},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                result = await resp.json()
                print(f"[GROUP] Backend notified for chat {chat_id}: {result}")
                return result
    except Exception as e:
        print(f"[GROUP] Backend notify failed for chat {chat_id}: {e}")
        return None

'''
            patched = patched[:insert_pos] + fn_code + patched[insert_pos:]
            applied += 1
            print("Patch 1: Added notify_backend_group() function")
        else:
            print("WARNING: Could not find insertion point for notify_backend_group()")
    else:
        print("Patch 1: notify_backend_group() already present, skipping")

    # ── Patch 2: Call notify_backend_group() in the my_chat_member handler ──
    # The bot saves to pending_groups.json; we add a backend call right after
    # Look for the pattern where it saves the group:
    #   pending_groups[str(chat_id)] = {...}
    #   save_json(PENDING_GROUPS_FILE, pending_groups)
    if "await notify_backend_group(" not in patched:
        # Find the save_json call for pending groups
        save_pattern = 'save_json(PENDING_GROUPS_FILE, pending_groups)'
        idx = patched.find(save_pattern)
        if idx != -1:
            eol = patched.index('\n', idx)
            # Get the indentation
            line_start = patched.rfind('\n', 0, idx) + 1
            indent = ''
            for ch in patched[line_start:]:
                if ch in (' ', '\t'):
                    indent += ch
                else:
                    break

            insert_code = f"\n{indent}await notify_backend_group(chat_id, chat_title)"
            patched = patched[:eol] + insert_code + patched[eol:]
            applied += 1
            print("Patch 2: Added notify_backend_group() call after pending_groups save")
        else:
            print("WARNING: Could not find save_json(PENDING_GROUPS_FILE, ...) pattern")
    else:
        print("Patch 2: notify_backend_group() call already present, skipping")

    if applied > 0:
        BOT_FILE.write_text(patched)
        print(f"\nApplied {applied} patches to {BOT_FILE}")
    else:
        print("\nNo patches needed — all already applied")

if __name__ == "__main__":
    main()
