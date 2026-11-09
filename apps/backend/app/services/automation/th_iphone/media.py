"""
th_iphone/media.py — Pipeline media pour iPhone (async).

Push un media sur l'iPhone, l'importe dans la galerie,
et nettoie apres publication.

Le flow :
  1. Telecharge depuis R2 (url) vers l'iPhone via MCP/curl
  2. Import dans la galerie via GalleryService tweak
  3. Le script de publish selectionne le 1er media (le plus recent)
  4. Cleanup : rm fichier + suppression galerie

Usage:
    from .media import push_media_via_mcp, cleanup_media
"""

import asyncio
import json
import random
import string
import time


IPHONE_TMP = "/var/mobile/Media/th_media"


def _random_name(ext=".jpg"):
    """Genere un nom de fichier unique."""
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return "th_%s_%d%s" % (rand, int(time.time()), ext)


async def push_media_via_mcp(driver, media_url, log=print, device=None,
                              market="FR", spoof=True, phone_id=None,
                              spoof_server=None):
    """Push un media dans la galerie iPhone.

    Pipeline:
    1. iPhone telecharge depuis le spoof server (qui spoofe les metadata)
       ou directement depuis l'URL si spoof=False
    2. Import dans la galerie via GalleryService tweak

    Args:
        driver: THDriver (pour MCP calls)
        media_url: URL du media (R2 ou autre)
        device: modele device pour le spoof (None = depuis KV ou random)
        market: marche pour GPS/timezone (defaut FR)
        spoof: True pour passer par le spoofer (defaut True)
        phone_id: ID du compte pour cohérence device (persisté en KV)
        spoof_server: URL du spoof server (override)

    Returns:
        dict {success, iphone_path, filename, error, spoofed}
    """
    log("   [media] push: %s" % media_url[:60])

    # 1. Determiner l'extension
    ext = ".jpg"
    if ".mp4" in media_url or "video" in media_url:
        ext = ".mp4"
    elif ".png" in media_url:
        ext = ".png"

    filename = _random_name(ext)
    iphone_path = "%s/%s" % (IPHONE_TMP, filename)

    # 2. URL de telechargement (spoof server ou direct)
    if spoof and ext != ".mp4" and spoof_server:
        import urllib.parse
        download_url = "%s/spoof?url=%s&market=%s" % (
            spoof_server,
            urllib.parse.quote(media_url, safe=""),
            market,
        )
        if device:
            download_url += "&device=%s" % urllib.parse.quote(device, safe="")
        if phone_id:
            download_url += "&phone_id=%s" % urllib.parse.quote(phone_id, safe="")
        log("   [media] via spoofer (phone_id=%s)" % (phone_id or device or "random"))
    else:
        download_url = media_url
        if spoof and ext == ".mp4":
            log("   [media] video: spoof skip (images only)")

    try:
        # 3. Creer le dossier sur iPhone
        await driver.ht._call("run_command", {
            "command": "mkdir -p %s" % IPHONE_TMP,
            "timeout": 5,
        })

        # 4. iPhone telecharge (depuis spoof server ou R2 direct)
        result = await driver.ht._call("run_command", {
            "command": 'curl -sL -o "%s" "%s" && echo "OK $(wc -c < "%s" | tr -d " ")" || echo "FAIL"' % (
                iphone_path, download_url, iphone_path),
            "timeout": 120,
        })
        out = ""
        if isinstance(result, dict) and "content" in result:
            out = result["content"][0].get("text", "")
            if isinstance(out, str) and "{" in out:
                try:
                    out = json.loads(out).get("output", out)
                except Exception:
                    pass

        if "FAIL" in str(out) or "OK" not in str(out):
            log("   [media] download KO: %s" % str(out)[:60])
            return {"success": False, "error": "download_failed"}

        log("   [media] telecharge: %s" % str(out).strip()[:40])

        # 5. Import galerie via GalleryService tweak
        ok = await _gallery_import(driver, iphone_path, log)
        if not ok:
            log("   [media] import galerie KO")
            return {"success": False, "error": "gallery_import_failed"}

        log("   [media] importe dans la galerie")
        await asyncio.sleep(2)

        return {
            "success": True,
            "iphone_path": iphone_path,
            "filename": filename,
            "spoofed": spoof and ext != ".mp4",
        }

    except Exception as e:
        log("   [media] erreur push: %s" % str(e)[:100])
        return {"success": False, "error": str(e)[:100]}


async def _gallery_import(driver, iphone_path, log=print):
    """Importe dans la galerie via GalleryService tweak (localhost:8192 sur iPhone)."""
    try:
        result = await driver.ht._call("run_command", {
            "command": 'curl -s -X POST http://localhost:8192/import '
                       '-H "Content-Type: application/json" '
                       '-d \'{"path":"%s"}\'' % iphone_path,
            "timeout": 15,
        })
        out = ""
        if isinstance(result, dict) and "content" in result:
            out = str(result["content"])
        if "ok" in out or "true" in out:
            return True
        log("   [gallery] import via MCP: %s" % out[:60])
        return False
    except Exception as e:
        log("   [gallery] MCP erreur: %s" % str(e)[:60])
        return False


async def cleanup_media(driver, iphone_path, log=print):
    """Supprime le fichier media temporaire de l'iPhone."""
    if not iphone_path:
        return
    try:
        await driver.ht._call("run_command", {
            "command": "rm -f %s" % iphone_path,
            "timeout": 5,
        })
        log("   [media] cleanup tmp: %s" % iphone_path)
    except Exception as e:
        log("   [media] cleanup KO: %s" % str(e)[:60])


async def cleanup_media_batch(driver, iphone_paths, log=print):
    """Supprime plusieurs fichiers media temporaires."""
    if not iphone_paths:
        return
    for p in iphone_paths:
        try:
            await driver.ht._call("run_command", {
                "command": "rm -f %s" % p,
                "timeout": 5,
            })
        except Exception:
            pass
    log("   [media] cleanup batch: %d fichiers tmp" % len(iphone_paths))


async def cleanup_gallery(driver, count, log=print):
    """Supprime les N photos les plus recentes de la galerie via GalleryService tweak."""
    log("   [gallery] suppression de %d photo(s)..." % count)
    try:
        result = await driver.ht._call("run_command", {
            "command": 'curl -s -X POST http://localhost:8192/delete '
                       '-H "Content-Type: application/json" '
                       '-d \'{"count":%d}\'' % count,
            "timeout": 15,
        })
        out = ""
        if isinstance(result, dict) and "content" in result:
            out = str(result["content"])
        if "ok" in out or "true" in out:
            log("   [gallery] %d photo(s) supprimee(s)" % count)
            return True
        log("   [gallery] suppression KO: %s" % out[:60])
        return False
    except Exception as e:
        log("   [gallery] erreur: %s" % str(e)[:60])
        return False


async def cleanup_all_media(driver, log=print):
    """Supprime tous les medias temporaires de l'iPhone."""
    try:
        await driver.ht._call("run_command", {
            "command": "rm -rf %s" % IPHONE_TMP,
            "timeout": 5,
        })
        log("   [media] cleanup all tmp media")
    except Exception:
        pass
