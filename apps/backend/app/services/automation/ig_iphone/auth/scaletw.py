"""
ig_iphone/auth/scaletw.py — Rotation de comptes via ScaleTweak (containers).

Appelle l'API HTTP ScaleController sur l'iPhone (via SSH tunnel).

Flow :
  1. API /switch {"name": target} → change le container actif
  2. API /kill-ig → kill Instagram
  3. IG se relance avec le bon container automatiquement

Ported from VPS — adapted to async + SSH tunnel (httpx).
"""

import asyncio
import json
from typing import Any, Callable

import httpx


async def _api(method: str, path: str, data: dict | None = None,
               ssh_port: int = 8085, timeout: int = 10) -> dict:
    """Appel API ScaleController via tunnel SSH.

    Le tunnel SSH forward le port local vers le port 8080 de l'iPhone.
    Le port est configurable (defaut 8085 = convention tunnel).
    """
    url = "http://127.0.0.1:%d%s" % (ssh_port, path)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                r = await client.get(url)
            else:
                r = await client.post(url, json=data or {})
            return r.json()
    except Exception as e:
        return {"error": str(e)}


async def list_containers(ssh_port: int = 8085, log: Callable = print) -> list:
    """Liste les containers ScaleTweak. Retourne liste de dicts."""
    log("-> ScaleTweak: liste containers")
    resp = await _api("GET", "/list", ssh_port=ssh_port)
    containers = resp.get("containers", [])
    active = resp.get("active", "")
    for c in containers:
        marker = " ◀ ACTIVE" if c.get("active") else ""
        log("   %s (%s) — %s %s%s" % (
            c.get("name", "?"), c.get("uuid", "?")[:8],
            c.get("device", ""), c.get("country", ""), marker))
    log("   %d containers" % len(containers))
    return containers


async def get_active_container(ssh_port: int = 8085, log: Callable = print) -> dict:
    """Retourne le container actif (dict)."""
    resp = await _api("GET", "/status", ssh_port=ssh_port)
    return resp


async def switch_container(target: str, ssh_port: int = 8085,
                           kill: bool = True, wait: int = 5,
                           log: Callable = print) -> bool:
    """Switch de container par nom ou UUID.

    Args:
        target: nom du container ou UUID
        kill: kill IG après le switch
        wait: secondes à attendre après le kill
    Returns:
        True si le switch a réussi
    """
    log("-> ScaleTweak: switch → %s" % target)

    # Déterminer si c'est un nom ou un UUID
    data = {}
    if len(target) == 36 and target.count("-") == 4:
        data["uuid"] = target
    else:
        data["name"] = target

    resp = await _api("POST", "/switch", data, ssh_port=ssh_port)
    result = resp.get("result", "")
    if "error" in resp:
        log("   ! switch error: %s" % resp["error"])
        return False

    log("   %s" % result)

    if kill:
        log("   killing IG...")
        await _api("POST", "/kill-ig", ssh_port=ssh_port)
        await asyncio.sleep(wait)
        log("   ready")

    return True


async def create_container(name: str, country: str = "FR", persona: str = "",
                           ssh_port: int = 8085, log: Callable = print) -> dict:
    """Crée un nouveau container.

    Args:
        name: nom du container
        country: FR, US, BR, ES, IT, GB, DE
        persona: nom pour le device (optionnel)
    Returns:
        résultat de la création
    """
    log("-> ScaleTweak: créer container '%s' (%s)" % (name, country))
    data = {"name": name, "country": country}
    if persona:
        data["persona"] = persona
    resp = await _api("POST", "/create", data, ssh_port=ssh_port)
    log("   %s" % resp.get("result", resp))
    return resp


async def delete_container(uuid: str, ssh_port: int = 8085,
                           log: Callable = print) -> dict:
    """Supprime un container par UUID."""
    log("-> ScaleTweak: supprimer %s" % uuid[:8])
    resp = await _api("POST", "/delete", {"uuid": uuid}, ssh_port=ssh_port)
    log("   %s" % resp.get("result", resp))
    return resp


async def extract_token(ssh_port: int = 8085, log: Callable = print) -> dict | None:
    """Extrait la session IG du container actif.

    Returns:
        dict avec sessionid, authorization, mid, ds_user_id
        ou None si pas de session
    """
    log("-> ScaleTweak: extraction session")
    resp = await _api("GET", "/export-session", ssh_port=ssh_port)
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


async def switch_and_extract(target: str, ssh_port: int = 8085,
                             wait: int = 8, log: Callable = print) -> dict | None:
    """Switch de container et extrait la session.

    Args:
        target: nom du container
        wait: secondes à attendre que IG redémarre
    Returns:
        dict session ou None
    """
    if not await switch_container(target, ssh_port=ssh_port, wait=wait, log=log):
        return None

    # Attendre que IG écrive la session
    log("   attente session extraction...")
    await asyncio.sleep(15)

    return await extract_token(ssh_port=ssh_port, log=log)


async def ensure_account(target: str, ssh_port: int = 8085,
                         log: Callable = print) -> bool:
    """Vérifie que le bon container est actif, switch si nécessaire.

    Args:
        target: nom du container cible
    Returns:
        True si le bon container est actif
    """
    status = await get_active_container(ssh_port=ssh_port, log=lambda x: None)
    current = status.get("name", "")

    if current == target:
        log("-> ScaleTweak: déjà sur '%s'" % target)
        return True

    return await switch_container(target, ssh_port=ssh_port, log=log)


async def health_check(ssh_port: int = 8085, log: Callable = print) -> bool:
    """Vérifie que ScaleController est accessible."""
    resp = await _api("GET", "/health", ssh_port=ssh_port)
    ok = resp.get("status") == "ok"
    if ok:
        log("-> ScaleTweak: controller OK")
    else:
        log("-> ScaleTweak: controller UNREACHABLE — %s" % resp)
    return ok


# ── Rétrocompatibilité ──────────────────────────────────────────────────────

async def get_current_username(driver, navigator, log: Callable = print) -> str | None:
    """Détecte le username du compte actuellement connecté via l'UI."""
    await navigator.go_profile()
    await asyncio.sleep(1)
    r = await driver.ht._call("get_ui_elements", {"clickable_only": False, "max_elements": 60})
    els = []
    if r:
        for c in r.get("content", []):
            if c.get("type") == "text":
                try:
                    data = json.loads(c["text"])
                    els = data.get("elements", [])
                except Exception:
                    pass
    for el in els:
        t = (el.get("text") or "")
        rect = el.get("rect", {})
        if rect.get("y", 999) < 70 and rect.get("x", 0) > 50 and rect.get("x", 0) < 250:
            if t and len(t) > 3 and len(t) < 35:
                if "." in t or "_" in t or t.islower():
                    return t
    return None
