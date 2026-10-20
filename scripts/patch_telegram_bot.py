#!/usr/bin/env python3
"""Patch telegram_bot.py to add backend integration (deep link + API calls).

Run on VPS:  python3 /root/scale-lab/scripts/patch_telegram_bot.py
"""
import os
import re
import shutil
import sys

BOT_FILE = "/root/telegram_bot.py"
BACKUP = BOT_FILE + ".bak_scalelab"

def patch():
    if not os.path.exists(BOT_FILE):
        print("ERROR: %s not found" % BOT_FILE)
        sys.exit(1)

    # Read original
    with open(BOT_FILE, "r", encoding="utf-8") as f:
        code = f.read()

    # Check if already patched
    if "BACKEND_URL" in code:
        print("Already patched (BACKEND_URL found). Skipping.")
        sys.exit(0)

    # Backup
    shutil.copy2(BOT_FILE, BACKUP)
    print("Backup: %s" % BACKUP)

    # ── Patch 1: Add BACKEND_URL + API_SECRET after DATA_DIR line ──
    code = code.replace(
        'DATA_DIR = "/root/telegram_bot"\nos.makedirs(DATA_DIR, exist_ok=True)',
        'DATA_DIR = "/root/telegram_bot"\nos.makedirs(DATA_DIR, exist_ok=True)\n'
        '\n'
        '# Scale Lab backend (same VPS)\n'
        'BACKEND_URL = "http://127.0.0.1:8000"\n'
        'API_SECRET = os.environ.get("API_SECRET", "")\n'
        'if not API_SECRET:\n'
        '    # Read from backend .env if available\n'
        '    try:\n'
        '        for line in open("/root/scale-lab/apps/backend/.env"):\n'
        '            if line.startswith("API_SECRET="):\n'
        '                API_SECRET = line.split("=", 1)[1].strip().strip(\'"\\\'\')\n'
        '    except: pass\n',
    )

    # ── Patch 2: Add notify_backend() after save_data() ──
    code = code.replace(
        '\n\n# ============ GROUP TEMPLATE ============',
        '\n\ndef notify_backend(endpoint, data):\n'
        '    """Call the Scale Lab backend API."""\n'
        '    if not API_SECRET:\n'
        '        print("[BOT] No API_SECRET, skipping backend call")\n'
        '        return {"ok": False, "error": "no_api_secret"}\n'
        '    try:\n'
        '        r = requests.post(\n'
        '            BACKEND_URL + endpoint,\n'
        '            json=data,\n'
        '            headers={"X-Scale-Token": API_SECRET},\n'
        '            timeout=10,\n'
        '        )\n'
        '        return r.json()\n'
        '    except Exception as e:\n'
        '        print("[BOT] Backend call failed: %s %s" % (endpoint, str(e)[:100]))\n'
        '        return {"ok": False, "error": str(e)}\n'
        '\n\n# ============ GROUP TEMPLATE ============',
    )

    # ── Patch 3: Replace /start handler ──
    # Find the /start block and replace it
    old_start = (
        '        if text.startswith("/start"):\n'
    )
    # Find the full block including the return
    start_idx = code.find(old_start)
    if start_idx == -1:
        print("ERROR: Could not find /start handler")
        sys.exit(1)

    # Find the next "return" + newline after /start
    return_after = code.find("            return\n", start_idx)
    if return_after == -1:
        print("ERROR: Could not find return after /start")
        sys.exit(1)
    end_of_block = return_after + len("            return\n")

    new_start = (
        '        if text.startswith("/start"):\n'
        '            parts = text.split(None, 1)\n'
        '            if len(parts) > 1:\n'
        '                persona_id = parts[1].strip()\n'
        '                user = msg.get("from", {})\n'
        '                result = notify_backend("/api/telegram/bot/start", {\n'
        '                    "persona_id": persona_id,\n'
        '                    "tg_user_id": user_id,\n'
        '                    "tg_username": user.get("username", ""),\n'
        '                    "tg_first_name": user.get("first_name", ""),\n'
        '                    "tg_lang": (user.get("language_code") or "fr")[:2],\n'
        '                })\n'
        '                if result.get("ok"):\n'
        '                    if result.get("status") == "already_linked":\n'
        '                        tg_send_message(chat_id, "\\u2705 Tu es d\\u00e9j\\u00e0 connect\\u00e9e \\u00e0 ScaleCrew !")\n'
        '                    else:\n'
        '                        tg_send_message(chat_id, "\\u2705 Inscription re\\u00e7ue ! Ton manager va te valider. Tu recevras tes briefs ici bient\\u00f4t.")\n'
        '                else:\n'
        '                    err = result.get("error", "")\n'
        '                    if "persona_not_found" in err:\n'
        '                        tg_send_message(chat_id, "\\u274c Lien invalide. Demande un nouveau lien \\u00e0 ton manager.")\n'
        '                    else:\n'
        '                        tg_send_message(chat_id, "\\u26a0\\ufe0f Probl\\u00e8me temporaire. R\\u00e9essaie dans quelques instants.")\n'
        '            else:\n'
        '                tg_send_message(chat_id, "\\U0001f44b Bienvenue ! Demande le lien d\\u0027inscription \\u00e0 ton manager, ou envoie-moi ton code d\\u0027acc\\u00e8s.")\n'
        '            return\n'
    )

    code = code[:start_idx] + new_start + code[end_of_block:]

    # ── Patch 4: Also notify backend when auth code succeeds ──
    old_auth = '                save_data("models.json", models)\n                tg_send_message(chat_id,'
    auth_idx = code.find(old_auth)
    if auth_idx != -1:
        # Find the save_data line for models.json in the auth code block
        insert_point = auth_idx + len('                save_data("models.json", models)\n')
        backend_notify = (
            '                # Notify backend\n'
            '                notify_backend("/api/telegram/bot/start", {\n'
            '                    "persona_id": entry["persona_id"],\n'
            '                    "tg_user_id": user_id,\n'
            '                    "tg_username": msg.get("from", {}).get("username", ""),\n'
            '                    "tg_first_name": msg.get("from", {}).get("first_name", ""),\n'
            '                })\n'
        )
        code = code[:insert_point] + backend_notify + code[insert_point:]

    # Write patched file
    with open(BOT_FILE, "w", encoding="utf-8") as f:
        f.write(code)

    print("Patched successfully!")
    print("Changes:")
    print("  1. Added BACKEND_URL + API_SECRET config")
    print("  2. Added notify_backend() helper")
    print("  3. /start now parses deep link persona_id and calls backend")
    print("  4. Auth code success also notifies backend")
    print("\nRestart the bot:  systemctl restart telegram-bot")


if __name__ == "__main__":
    patch()
