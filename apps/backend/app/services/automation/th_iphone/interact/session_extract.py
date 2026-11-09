"""
th_iphone/interact/session_extract.py — Extraction session Threads (async).

Extrait les cookies de session, verifie le statut du compte
(checkpoint, ban, etc.) via l'API privee.

Usage:
    from ..interact.session_extract import extract_session_from_device, check_account_status
"""

import asyncio
import json
import logging

import httpx

logger = logging.getLogger("automation.th_session_extract")

IG_API_BASE = "https://i.instagram.com/api/v1"


async def extract_session_from_device(driver, log=print):
    """Extrait les cookies de session Threads depuis le device iOS."""
    log("-> Extraction session Threads")

    try:
        r = await driver.ht._call("run_command", {
            "command": (
                'find /var/mobile/Containers/Data/Application -maxdepth 1 -type d | '
                'while read d; do if [ -f "$d/Library/Preferences/com.burbn.barcelona.plist" ]; then '
                'echo "$d"; break; fi; done'
            ),
            "timeout": 10,
        })
        data_path = ""
        if isinstance(r, dict) and "content" in r:
            raw = r["content"][0].get("text", "")
            data_path = raw.strip()

        if not data_path:
            log("   ! container Threads non trouve")
            return None

        log("   container: %s" % data_path[-40:])

        r2 = await driver.ht._call("run_command", {
            "command": (
                "python3 -c \"import plistlib,json;f=open('%s/Library/Preferences/com.burbn.barcelona.plist','rb');"
                "d=plistlib.load(f);out={};"
                "[out.update({k:str(v)}) for k,v in d.items() if any(x in k.lower() for x in "
                "['session','device','csrf','ds_user','mid','token','auth'])];"
                "print(json.dumps(out))\"" % data_path
            ),
            "timeout": 10,
        })

        session_data = {}
        if isinstance(r2, dict) and "content" in r2:
            raw = r2["content"][0].get("text", "")
            try:
                session_data = json.loads(raw.strip())
            except Exception:
                log("   ! parsing plist KO: %s" % raw[:100])

        if session_data:
            log("   session extraite: %d cles" % len(session_data))
        else:
            log("   ! aucune donnee de session trouvee")

        return session_data if session_data else None

    except Exception as e:
        log("   ! erreur extraction: %s" % str(e)[:100])
        return None


async def check_account_status(sessionid, user_id=None, log=print, proxy=None):
    """Verifie le statut du compte via l'API privee IG."""
    log("-> Verification statut compte")

    status = {
        "active": False,
        "checkpoint": False,
        "banned": False,
        "restricted": False,
        "followers": None,
        "following": None,
        "posts": None,
        "error": None,
    }

    if not sessionid:
        status["error"] = "no_sessionid"
        return status

    headers = {
        "Cookie": "sessionid=%s" % sessionid,
        "User-Agent": "Barcelona 341.0.0.36.109 Android",
        "X-IG-App-ID": "238260118697367",
    }

    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=10) as client:
            # Test 1: timeline feed
            r = await client.get("%s/feed/timeline/" % IG_API_BASE, headers=headers)

            if r.status_code == 200:
                status["active"] = True
                log("   ✅ session active")

            elif r.status_code == 401:
                status["error"] = "session_expired"
                log("   ❌ session expiree")
                return status

            elif r.status_code == 400:
                try:
                    body = r.json()
                except Exception:
                    body = {}
                if "challenge" in str(body).lower():
                    status["checkpoint"] = True
                    status["error"] = "checkpoint"
                    log("   ⚠️  CHECKPOINT")
                elif "feedback" in str(body).lower():
                    status["restricted"] = True
                    status["error"] = "action_blocked"
                    log("   ⚠️  action bloquee")
                else:
                    status["error"] = "unknown_400"
                    log("   ❌ erreur 400: %s" % str(body)[:100])
                return status

            elif r.status_code == 429:
                status["error"] = "rate_limited"
                log("   ⚠️  rate limited")
                return status

            # Test 2: info du compte
            if user_id:
                r2 = await client.get(
                    "%s/users/%s/info/" % (IG_API_BASE, user_id),
                    headers=headers,
                )
                if r2.status_code == 200:
                    data = r2.json()
                    user = data.get("user", {})
                    status["followers"] = user.get("follower_count")
                    status["following"] = user.get("following_count")
                    status["posts"] = user.get("media_count")
                    log("   followers=%s following=%s posts=%s" % (
                        status["followers"], status["following"], status["posts"]))

    except httpx.TimeoutException:
        status["error"] = "timeout"
        log("   ❌ timeout")
    except Exception as e:
        status["error"] = str(e)[:100]
        log("   ❌ erreur: %s" % str(e)[:100])

    return status


async def full_health_check(driver, sessionid=None, user_id=None, log=print, proxy=None):
    """Check complet : extraction session + verification statut."""
    result = {"session": None, "status": None}

    if not sessionid:
        session = await extract_session_from_device(driver, log=log)
        result["session"] = session
        if session:
            sessionid = session.get("sessionid", "")

    if sessionid:
        status = await check_account_status(sessionid, user_id=user_id, log=log, proxy=proxy)
        result["status"] = status

    return result
