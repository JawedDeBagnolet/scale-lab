"""
ig_iphone/media.py — Pipeline media pour iPhone.

Push un media sur l'iPhone, l'importe dans la galerie,
et nettoie apres publication.

Le flow validé (testé et fonctionnel) :
  1. VPS telecharge depuis R2 (avec auth Bearer) vers /tmp local VPS
  2. SCP vers iPhone via tunnel SSH (port 2223)
  3. MTOUCH /import — appel HTTP direct du VPS vers 127.0.0.1:8191 (tunnel) → Camera Roll
  4. Le script de publish selectionne le 1er media (le plus recent)
  5. Cleanup : rm fichier + suppression galerie

Usage:
    from ig_iphone.media import push_media_to_gallery, cleanup_media
"""

import asyncio
import logging
import os
import random
import string
import time

logger = logging.getLogger("ig_iphone.media")

# ── Constants ─────────────────────────────────────────────────────────────────

IPHONE_TMP = "/var/mobile/Media/th_media"
LOCAL_TMP = "/tmp/th_media_staging"
SPOOF_SERVER = "http://127.0.0.1:8502"  # VPS localhost
MTOUCH_PORT_IPHONE = 8195  # RTInject port sur l'iPhone (SpringBoard, /import)
MTOUCH_PORT_VPS = 8191     # RTInject tunnel sur le VPS (127.0.0.1:8191 → iPhone:8195)

# SSH tunnel ports (VPS → iPhone via reverse tunnel)
DEFAULT_SSH_PORT = 2223
SSH_KEY = "/root/.ssh/id_iphone"


def _random_name(ext=".jpg"):
    """Genere un nom de fichier unique."""
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return "th_%s_%d%s" % (rand, int(time.time()), ext)


# ── Core pipeline functions ───────────────────────────────────────────────────

async def _vps_download(url: str, local_path: str, auth_header: str | None = None,
                        log=logger.info) -> bool:
    """Telecharge un fichier depuis une URL sur le VPS local."""
    import httpx

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            log("   [media] download HTTP %d pour %s" % (resp.status_code, url[:60]))
            return False
        with open(local_path, "wb") as f:
            f.write(resp.content)
        size_kb = len(resp.content) // 1024
        log("   [media] telecharge %d Ko -> %s" % (size_kb, local_path))
        if size_kb < 1:
            log("   [media] ⚠ fichier trop petit (%d octets)" % len(resp.content))
            return False
        return True
    except Exception as e:
        log("   [media] erreur download: %s" % str(e)[:100])
        return False


async def _scp_to_iphone(local_path: str, remote_path: str,
                          ssh_port: int = DEFAULT_SSH_PORT,
                          log=logger.info) -> bool:
    """SCP un fichier du VPS vers l'iPhone via le tunnel SSH."""
    from app.services.dispatch import _ssh_exec, DEFAULT_SSH_PORT as _DSP

    # D'abord creer le dossier sur l'iPhone
    ok, _ = await _ssh_exec(ssh_port, "mkdir -p %s" % os.path.dirname(remote_path))
    if not ok:
        log("   [media] mkdir echoue sur iPhone")

    # SCP via subprocess (asyncio)
    import subprocess
    cmd = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=10",
        "-o", "LogLevel=ERROR",
        "-P", str(ssh_port),
        "-i", SSH_KEY,
        local_path,
        "root@127.0.0.1:%s" % remote_path,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode == 0:
            log("   [media] SCP OK -> %s" % remote_path)
            return True
        else:
            err = (stderr or b"").decode("utf-8", errors="replace")[:100]
            log("   [media] SCP echoue (rc=%d): %s" % (proc.returncode, err))
            return False
    except asyncio.TimeoutError:
        log("   [media] SCP timeout")
        return False
    except Exception as e:
        log("   [media] SCP erreur: %s" % str(e)[:100])
        return False


async def _mtouch_import(iphone_path: str, ssh_port: int = DEFAULT_SSH_PORT,
                          log=logger.info) -> bool:
    """Importe un fichier dans la galerie iOS via MTOUCH /import.

    Methode principale : appel HTTP direct du VPS vers 127.0.0.1:8191 (tunnel).
    Fallback : SSH curl vers iPhone localhost:8091 (ne marche pas sur tous les iPhones).
    """
    import httpx
    import json

    url = "http://127.0.0.1:%d/import" % MTOUCH_PORT_VPS
    payload = {"path": iphone_path}

    # ── Methode 1 : appel HTTP direct depuis le VPS ──
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
        data = resp.json()
        if data.get("ok"):
            log("   [gallery] MTOUCH import OK (%s)" % data.get("type", "?"))
            return True
        else:
            log("   [gallery] MTOUCH import KO: %s" % data.get("error", str(data)[:60]))
            return False
    except httpx.ConnectError:
        log("   [gallery] MTOUCH tunnel 8191 injoignable, essai SSH fallback...")
    except Exception as e:
        log("   [gallery] MTOUCH direct erreur: %s — essai SSH fallback..." % str(e)[:80])

    # ── Methode 2 (fallback) : SSH curl vers iPhone ──
    try:
        from app.services.dispatch import _ssh_exec

        payload_json = json.dumps(payload)
        payload_escaped = payload_json.replace("'", "'\\''")
        cmd = (
            "curl -s --max-time 15 -X POST http://127.0.0.1:%d/import "
            "-H 'Content-Type: application/json' "
            "-d '%s'" % (MTOUCH_PORT_IPHONE, payload_escaped)
        )

        ok, output = await _ssh_exec(ssh_port, cmd, timeout=20)
        if not ok:
            log("   [gallery] MTOUCH SSH fallback echoue: %s" % str(output)[:80])
            return False

        if not isinstance(output, str):
            output = output.decode("utf-8", errors="replace")
        data = json.loads(output)
        if data.get("ok"):
            log("   [gallery] MTOUCH import OK via SSH (%s)" % data.get("type", "?"))
            return True
        else:
            log("   [gallery] MTOUCH SSH KO: %s" % data.get("error", output[:60]))
            return False
    except Exception as e:
        log("   [gallery] MTOUCH SSH fallback erreur: %s" % str(e)[:80])
        return False


# ── Public API ────────────────────────────────────────────────────────────────

async def push_media_to_gallery(
    media_url: str,
    *,
    auth_header: str | None = None,
    ssh_port: int = DEFAULT_SSH_PORT,
    spoof: bool = False,
    market: str = "FR",
    device: str | None = None,
    phone_id: str | None = None,
    log=logger.info,
) -> dict:
    """Push un media dans la galerie iPhone — pipeline complet.

    Pipeline validé :
      1. VPS telecharge depuis R2/spoof server
      2. SCP vers iPhone port 2223
      3. MTOUCH /import port 8091 → Camera Roll

    Args:
        media_url: URL du media (R2 ou autre)
        auth_header: "Bearer <token>" pour les URLs R2 authentifiees
        ssh_port: Port SSH tunnel (defaut 2223)
        spoof: True pour passer par le spoofer EXIF
        market: Marche pour GPS/timezone du spoof
        device: Modele device pour le spoof
        phone_id: ID du compte pour coherence device

    Returns:
        dict {success, iphone_path, filename, error}
    """
    log("   [media] push: %s" % media_url[:60])

    # 1. Determiner l'extension
    ext = ".jpg"
    if ".mp4" in media_url or "video" in media_url:
        ext = ".mp4"
    elif ".png" in media_url:
        ext = ".png"

    filename = _random_name(ext)
    local_path = os.path.join(LOCAL_TMP, filename)
    iphone_path = "%s/%s" % (IPHONE_TMP, filename)

    try:
        # 2. URL de telechargement (spoof server ou direct avec fallback)
        dl_ok = False
        if spoof and ext != ".mp4":
            import urllib.parse
            download_url = "%s/spoof?url=%s&market=%s" % (
                SPOOF_SERVER,
                urllib.parse.quote(media_url, safe=""),
                market,
            )
            if device:
                download_url += "&device=%s" % urllib.parse.quote(device, safe="")
            if phone_id:
                download_url += "&phone_id=%s" % urllib.parse.quote(phone_id, safe="")
            log("   [media] via spoofer (phone_id=%s)" % (phone_id or device or "random"))
            # Forward auth header to spoof server so it can download from R2
            dl_ok = await _vps_download(download_url, local_path, auth_header=auth_header, log=log)
            if not dl_ok:
                log("   [media] ⚠ spoofer echoue, fallback download direct")

        if not dl_ok:
            # Fallback: download direct depuis R2 (sans spoof EXIF)
            dl_ok = await _vps_download(media_url, local_path, auth_header=auth_header, log=log)

        if not dl_ok:
            return {"success": False, "error": "download_failed"}

        # 3. SCP vers iPhone
        scp_ok = await _scp_to_iphone(local_path, iphone_path, ssh_port=ssh_port, log=log)
        if not scp_ok:
            return {"success": False, "error": "scp_failed"}

        # 4. Import galerie via MTOUCH
        import_ok = await _mtouch_import(iphone_path, ssh_port=ssh_port, log=log)
        if not import_ok:
            log("   [media] ⚠ MTOUCH import echoue — fichier present sur iPhone à %s" % iphone_path)
            return {"success": False, "error": "gallery_import_failed", "iphone_path": iphone_path}

        # 5. Cleanup local VPS
        try:
            os.remove(local_path)
        except OSError:
            pass

        log("   [media] ✓ media importe dans la galerie")
        await asyncio.sleep(2)  # Laisser le temps a iOS de mettre a jour la galerie

        return {
            "success": True,
            "iphone_path": iphone_path,
            "filename": filename,
        }

    except Exception as e:
        log("   [media] erreur push: %s" % str(e)[:100])
        # Cleanup local
        try:
            os.remove(local_path)
        except OSError:
            pass
        return {"success": False, "error": str(e)[:100]}


# ── Legacy wrappers (backward compatibility) ──────────────────────────────────

async def push_media_via_mcp(driver, media_url, log=print, device=None,
                              market="FR", spoof=True, phone_id=None,
                              auth_header=None):
    """Legacy wrapper — redirige vers push_media_to_gallery."""
    from app.config import settings
    if not auth_header:
        auth_header = "Bearer %s" % settings.api_secret

    return await push_media_to_gallery(
        media_url,
        auth_header=auth_header,
        spoof=spoof,
        market=market,
        device=device,
        phone_id=phone_id,
        log=log,
    )


async def push_media_via_scp(media_url, log=print, spoof_profile=None,
                              auth_header=None):
    """Legacy wrapper — redirige vers push_media_to_gallery."""
    from app.config import settings
    if not auth_header:
        auth_header = "Bearer %s" % settings.api_secret

    return await push_media_to_gallery(
        media_url,
        auth_header=auth_header,
        spoof=bool(spoof_profile),
        log=log,
    )


# ── Cleanup ───────────────────────────────────────────────────────────────────

async def cleanup_media(driver, iphone_path, log=print):
    """Supprime le fichier media temporaire de l'iPhone."""
    if not iphone_path:
        return

    from app.services.dispatch import _ssh_exec
    try:
        ok, _ = await _ssh_exec(DEFAULT_SSH_PORT, "rm -f %s" % iphone_path)
        if ok:
            log("   [media] cleanup tmp: %s" % iphone_path)
        else:
            log("   [media] cleanup SSH echoue pour %s" % iphone_path)
    except Exception as e:
        log("   [media] cleanup KO: %s" % str(e)[:60])


async def cleanup_media_batch(driver, iphone_paths, log=print):
    """Supprime plusieurs fichiers media temporaires."""
    if not iphone_paths:
        return

    from app.services.dispatch import _ssh_exec
    paths_str = " ".join('"%s"' % p for p in iphone_paths)
    try:
        await _ssh_exec(DEFAULT_SSH_PORT, "rm -f %s" % paths_str)
    except Exception:
        pass
    log("   [media] cleanup batch: %d fichiers tmp" % len(iphone_paths))


async def cleanup_gallery_via_mtouch(count: int, ssh_port: int = DEFAULT_SSH_PORT,
                                      log=logger.info) -> bool:
    """Supprime les N photos les plus recentes via MTOUCH /delete.

    Methode principale : HTTP direct VPS → 127.0.0.1:8191
    Fallback : SSH curl vers iPhone localhost:8091
    """
    import httpx
    import json

    log("   [gallery] suppression de %d photo(s)..." % count)
    url = "http://127.0.0.1:%d/delete" % MTOUCH_PORT_VPS
    payload = {"count": count}

    # ── Methode 1 : HTTP direct ──
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
        data = resp.json()
        if data.get("ok"):
            log("   [gallery] %d photo(s) supprimee(s)" % data.get("deleted", count))
            return True
        log("   [gallery] suppression KO: %s" % data.get("error", "?"))
        return False
    except httpx.ConnectError:
        log("   [gallery] MTOUCH tunnel 8191 injoignable, essai SSH fallback...")
    except Exception as e:
        log("   [gallery] MTOUCH direct erreur: %s — essai SSH fallback..." % str(e)[:80])

    # ── Methode 2 (fallback) : SSH curl ──
    try:
        from app.services.dispatch import _ssh_exec

        payload_json = json.dumps(payload).replace("'", "'\\''")
        cmd = (
            "curl -s --max-time 15 -X POST http://127.0.0.1:%d/delete "
            "-H 'Content-Type: application/json' "
            "-d '%s'" % (MTOUCH_PORT_IPHONE, payload_json)
        )
        ok, output = await _ssh_exec(ssh_port, cmd, timeout=20)
        if not ok:
            log("   [gallery] suppression SSH fallback echoue")
            return False
        data = json.loads(output if isinstance(output, str) else output.decode())
        if data.get("ok"):
            log("   [gallery] %d photo(s) supprimee(s) via SSH" % data.get("deleted", count))
            return True
        log("   [gallery] suppression SSH KO: %s" % data.get("error", "?"))
        return False
    except Exception as e:
        log("   [gallery] suppression SSH fallback erreur: %s" % str(e)[:60])
        return False


# Legacy alias
def cleanup_gallery(driver, count, log=print):
    """Synchronous wrapper — prefer cleanup_gallery_via_mtouch."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context, create a task
            return asyncio.ensure_future(cleanup_gallery_via_mtouch(count, log=log))
        return loop.run_until_complete(cleanup_gallery_via_mtouch(count, log=log))
    except Exception:
        return False


async def cleanup_all_media(driver=None, log=print):
    """Supprime tous les medias temporaires de l'iPhone."""
    from app.services.dispatch import _ssh_exec
    try:
        await _ssh_exec(DEFAULT_SSH_PORT, "rm -rf %s" % IPHONE_TMP)
        log("   [media] cleanup all tmp media")
    except Exception:
        pass
