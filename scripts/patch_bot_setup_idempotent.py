#!/usr/bin/env python3
"""Patch telegram_bot.py: make setup_group idempotent — skip if already set up."""

from pathlib import Path

BOT_FILE = Path("/root/telegram_bot.py")
src = BOT_FILE.read_text()

if "already set up, returning existing" in src:
    print("Already patched — skipping")
    exit(0)

# Find the setup_group function and add idempotency check
OLD = '''def setup_group(chat_id, persona_id):
    """Create template topics in a group and link to persona."""
    groups = load_data("groups.json", {})
    topic_ids = {}'''

NEW = '''def setup_group(chat_id, persona_id):
    """Create template topics in a group and link to persona."""
    groups = load_data("groups.json", {})

    # Idempotent: if already set up with topics, return existing data
    existing = groups.get(str(chat_id))
    if existing and existing.get("topics"):
        print("[BOT] Group %s already set up, returning existing data" % chat_id)
        existing["persona_id"] = persona_id
        groups[str(chat_id)] = existing
        save_data("groups.json", groups)
        return existing

    topic_ids = {}'''

if OLD not in src:
    print("ERROR: could not find setup_group function signature")
    exit(1)

patched = src.replace(OLD, NEW, 1)
BOT_FILE.write_text(patched)
print("Done — setup_group is now idempotent")
print("Restart with: systemctl restart telegram-bot")
