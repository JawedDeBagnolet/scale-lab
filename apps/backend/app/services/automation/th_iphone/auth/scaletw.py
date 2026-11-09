"""
th_iphone/auth/scaletw.py — Rotation de comptes via ScaleTweak pour Threads (async).

Appelle l'API HTTP ScaleController sur l'iPhone via tunnel SSH.

Usage:
    from ..auth.scaletw import switch_container, list_containers, extract_token
"""

import asyncio
import json
import logging

import httpx

logger = logging.getLogger("automation.th_scaletw")

# Default port — overridden by DeviceSession context
DEFAULT_SCALE_PORT = 8085


async def _api(method, path, data=None, timeout=10, base_url=None):
    """Appel API ScaleController (async)."""
    url = (base_url or ("http://127.0.0.1:%d" % DEFAULT_SCALE_PORT)) + path
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                r = await client.get(url)
            else:
                r = await client.post(url, json=data or {})
            return r.json()
    except Exception as e:
        return {"error": str(e)}


async def list_containers(log=print, base_url=None):
    """Liste les containers ScaleTweak. Retourne liste de dicts."""
    log("-> ScaleTweak: liste containers")
    resp = await _api("GET", "/list", base_url=base_url)
    containers = resp.get("containers", [])
    for c in containers:
        marker = " ◀ ACTIVE" if c.get("active") else ""
        log("   %s (%s) — %s %s%s" % (
            c.get("name", "?"), c.get("uuid", "?")[:8],
            c.get("device", ""), c.get("country", ""), marker))
    log("   %d containers" % len(containers))
    return containers


async def get_active_container(log=print, base_url=None):
    """Retourne le container actif (dict)."""
    resp = await _api("GET", "/status", base_url=base_url)
    return resp


async def switch_container(target, log=print, kill=True, wait=5, base_url=None):
    """Switch de container par nom ou UUID."""
    log("-> ScaleTweak: switch → %s" % target)

    data = {}
    if len(target) == 36 and target.count("-") == 4:
        data["uuid"] = target
    else:
        data["name"] = target

    resp = await _api("POST", "/switch", data, base_url=base_url)
    result = resp.get("result", "")
    if "error" in resp:
        log("   ! switch error: %s" % resp["error"])
        return False

    log("   %s" % result)

    if kill:
        log("   killing IG...")
        await _api("POST", "/kill-ig", base_url=base_url)
        await asyncio.sleep(wait)
        log("   ready")

    return True


async def create_container(name, country="FR", persona="", log=print, base_url=None):
    """Crée un nouveau container."""
    log("-> ScaleTweak: créer container '%s' (%s)" % (name, country))
    data = {"name": name, "country": country}
    if persona:
        data["persona"] = persona
    resp = await _api("POST", "/create", data, base_url=base_url)
    log("   %s" % resp.get("result", resp))
    return resp


async def delete_container(uuid, log=print, base_url=None):
    """Supprime un container par UUID."""
    log("-> ScaleTweak: supprimer %s" % uuid[:8])
    resp = await _api("POST", "/delete", {"uuid": uuid}, base_url=base_url)
    log("   %s" % resp.get("result", resp))
    return resp


async def extract_token(log=print, base_url=None):
    """Extrait la session du container actif."""
    log("-> ScaleTweak: extraction session")
    resp = await _api("GET", "/export-session", base_url=base_url)
    session = resp.get("session", {})

    if session.get("sessionid"):
        log("   ds_user_id: %s" % session.get("ds_user_id", "?"))
        log("   sessionid: %s..." % session.get("sessionid", "")[:20])
        log("   mid: %s" % ("YES" if session.get("mid") else "NO"))
        return {
            "sessionid": session.get("sessionid"),
            "ds_user_id": session.get("ds_user_id"),
            "mid": session.get("mid"),
            "authorization": resp.get("all_cookies", {}).get("authorization"),
            "container_uuid": resp.get("uuid"),
            "container_name": resp.get("name"),
        }
    else:
        log("   ! pas de session active")
        return None


async def switch_and_extract(target, log=print, wait=8, base_url=None):
    """Switch de container et extrait la session."""
    if not await switch_container(target, log=log, wait=wait, base_url=base_url):
        return None

    log("   attente session extraction...")
    await asyncio.sleep(15)

    return await extract_token(log=log, base_url=base_url)


async def ensure_account(target, log=print, base_url=None):
    """Vérifie que le bon container est actif, switch si nécessaire."""
    status = await get_active_container(log=lambda x: None, base_url=base_url)
    current = status.get("name", "")

    if current == target:
        log("-> ScaleTweak: déjà sur '%s'" % target)
        return True

    return await switch_container(target, log=log, base_url=base_url)


async def health_check(log=print, base_url=None):
    """Vérifie que ScaleController est accessible."""
    resp = await _api("GET", "/health", base_url=base_url)
    ok = resp.get("status") == "ok"
    if ok:
        log("-> ScaleTweak: controller OK")
    else:
        log("-> ScaleTweak: controller UNREACHABLE — %s" % resp)
    return ok
