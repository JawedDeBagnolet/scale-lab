"""
th_iphone/media.py — Pipeline media pour iPhone.

Push un media sur l'iPhone, l'importe dans la galerie,
et nettoie apres publication.

Le flow :
  1. Telecharge depuis R2 (url) vers /tmp local Mac
  2. Spoof metadata via spoofer.py
  3. SCP vers iPhone /var/tmp/
  4. importmedia → Camera Roll
  5. Le script de publish selectionne le 1er media (le plus recent)
  6. Cleanup : rm fichier + suppression galerie

Usage:
    from th_iphone.media import push_media, cleanup_media
"""

import os
import asyncio
import time
import subprocess
import requests
import random
import string


IPHONE_IP = "192.168.1.133"
IPHONE_TMP = "/var/mobile/Media/th_media"
IMPORTMEDIA = "/var/jb/usr/bin/importmedia"
LOCAL_TMP = "/tmp/th_media_staging"
SPOOF_SERVER = "http://77.42.124.107:8502"


def _random_name(ext=".jpg"):
    """Genere un nom de fichier unique."""
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return "th_%s_%d%s" % (rand, int(time.time()), ext)


def _ssh_cmd(cmd, timeout=15):
    """Execute une commande SSH sur l'iPhone."""
    r = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
         "root@%s" % IPHONE_IP, cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return r.stdout.strip(), r.returncode


def _scp_to_iphone(local_path, remote_path, timeout=30):
    """SCP un fichier vers l'iPhone."""
    r = subprocess.run(
        ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
         local_path, "root@%s:%s" % (IPHONE_IP, remote_path)],
        capture_output=True, text=True, timeout=timeout
    )
    return r.returncode == 0


async def push_media_via_mcp(driver, media_url, log=print, device=None, market="FR", spoof=True, phone_id=None):
    """Push un media dans la galerie iPhone.

    Pipeline:
    1. iPhone telecharge depuis le spoof server (qui spoofe les metadata)
       ou directement depuis l'URL si spoof=False
    2. Frida injecte dans SpringBoard appelle UIImageWriteToSavedPhotosAlbum

    Args:
        driver: THDriver (pour MCP calls)
        media_url: URL du media (R2 ou autre)
        device: modele device pour le spoof (None = depuis KV ou random)
        market: marche pour GPS/timezone (defaut FR)
        spoof: True pour passer par le spoofer (defaut True)
        phone_id: ID du compte pour cohérence device (persisté en KV)

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

    # Default device to iPhone X for iPhone containers
    if not device:
        device = "iPhone X"

    # 2. URL de telechargement (spoof server ou direct)
    if spoof and ext != ".mp4":  # Le spoof ne marche que pour les images
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
            "command": 'curl -sL -o "%s" "%s" && echo "OK $(wc -c < "%s" | tr -d " ")" || echo "FAIL"' % (iphone_path, download_url, iphone_path),
            "timeout": 120,
        })
        out = ""
        if isinstance(result, dict) and "content" in result:
            out = result["content"][0].get("text", "")
            if isinstance(out, str) and "{" in out:
                import json as _j
                try:
                    out = _j.loads(out).get("output", out)
                except:
                    pass

        if "FAIL" in str(out) or "OK" not in str(out):
            log("   [media] download KO: %s" % str(out)[:60])
            return {"success": False, "error": "download_failed"}

        log("   [media] telecharge: %s" % str(out).strip()[:40])

        # 5. Import galerie via Frida dans SpringBoard
        ok = _frida_save_to_gallery(iphone_path, log)
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


GALLERY_SERVICE = "http://192.168.1.133:8192"


async def _frida_save_to_gallery(iphone_path, log=print, driver=None):
    """Importe dans la galerie via GalleryService tweak (localhost:8192 sur iPhone)."""
    import requests as _req

    # Si driver dispo, passer par MCP (fonctionne depuis le VPS)
    if driver:
        try:
            result = await driver.ht._call("run_command", {
                "command": 'curl -s -X POST http://localhost:8192/import -H "Content-Type: application/json" -d \'{"path":"%s"}\'' % iphone_path,
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

    # Fallback : appel direct (si on est sur le reseau local)
    try:
        resp = _req.post("%s/import" % GALLERY_SERVICE, json={"path": iphone_path}, timeout=15)
        data = resp.json()
        if data.get("ok"):
            return True
        log("   [gallery] import KO: %s" % data.get("error", "?"))
        return False
    except Exception as e:
        log("   [gallery] erreur: %s" % str(e)[:100])
        return False


async def push_media_via_scp(media_url, log=print, spoof_profile=None):
    """Push un media sur l'iPhone via SCP + SSH importmedia.

    Alternative a push_media_via_mcp si MCP write_file est trop lent
    pour les gros fichiers (videos).

    Returns:
        dict {success, iphone_path, filename, error}
    """
    log("   [media] push via SCP: %s" % media_url[:60])

    ext = ".jpg"
    if ".mp4" in media_url or "video" in media_url:
        ext = ".mp4"
    elif ".png" in media_url:
        ext = ".png"

    filename = _random_name(ext)
    local_path = os.path.join(LOCAL_TMP, filename)
    iphone_path = "%s/%s" % (IPHONE_TMP, filename)

    try:
        # 1. Telecharger
        os.makedirs(LOCAL_TMP, exist_ok=True)
        r = requests.get(media_url, timeout=60)
        with open(local_path, "wb") as f:
            f.write(r.content)
        log("   [media] telecharge (%d Ko)" % (len(r.content) // 1024))

        # 2. Spoof
        if spoof_profile and ext in (".jpg", ".png"):
            try:
                from spoofer import spoof_file
                spoofed = local_path.replace(".", "_spoofed.")
                spoof_file(local_path, spoofed, profile=spoof_profile)
                os.remove(local_path)
                os.rename(spoofed, local_path)
                log("   [media] spoofed")
            except Exception as e:
                log("   [media] spoof skip: %s" % str(e)[:60])

        # 3. Creer dossier + SCP
        _ssh_cmd("mkdir -p %s" % IPHONE_TMP)
        if not _scp_to_iphone(local_path, iphone_path):
            log("   [media] SCP echoue")
            return {"success": False, "error": "scp_failed"}

        # 4. Import galerie
        out, code = _ssh_cmd("%s %s" % (IMPORTMEDIA, iphone_path))
        log("   [media] importmedia: %s" % (out or "OK"))

        # 5. Cleanup local
        os.remove(local_path)

        await asyncio.sleep(2)
        return {"success": True, "iphone_path": iphone_path, "filename": filename}

    except Exception as e:
        log("   [media] erreur: %s" % str(e)[:100])
        if os.path.exists(local_path):
            os.remove(local_path)
        return {"success": False, "error": str(e)[:100]}


async def cleanup_media(driver, iphone_path, log=print):
    """Supprime le fichier media temporaire de l'iPhone.
    Appeler cleanup_gallery apres pour nettoyer la galerie.
    """
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
        except:
            pass
    log("   [media] cleanup batch: %d fichiers tmp" % len(iphone_paths))


def cleanup_gallery(driver, count, log=print):
    """Supprime les N photos les plus recentes de la galerie via GalleryService tweak."""
    import requests as _req

    log("   [gallery] suppression de %d photo(s)..." % count)

    try:
        resp = _req.post("%s/delete" % GALLERY_SERVICE, json={"count": count}, timeout=15)
        data = resp.json()
        if data.get("ok"):
            log("   [gallery] %d photo(s) supprimee(s)" % data.get("deleted", count))
            return True
        else:
            log("   [gallery] suppression KO: %s" % data.get("error", "?"))
            return False
    except Exception as e:
        log("   [gallery] erreur: %s" % str(e)[:60])
        return False


async def ensure_delete_script(driver, log=print):
    """Verifie que le script delete_photos.py est present sur l'iPhone."""
    try:
        result = await driver.ht._call("run_command", {
            "command": "test -f /var/tmp/delete_photos.py && echo EXISTS || echo MISSING",
            "timeout": 5,
        })
        out = ""
        if isinstance(result, dict) and "content" in result:
            raw = result["content"][0].get("text", "")
            import json as _j
            try:
                out = _j.loads(raw).get("output", raw)
            except:
                out = raw

        if "MISSING" in str(out):
            log("   [gallery] deploiement delete_photos.py...")
            _deploy_delete_script(driver, log)
    except:
        pass


async def _deploy_delete_script(driver, log=print):
    """Deploie le script de suppression sur l'iPhone."""
    script = (
        'cat > /var/tmp/delete_photos.py << \'PYEOF\'\n'
        'import subprocess, sys, time\n'
        'n = int(sys.argv[1]) if len(sys.argv) > 1 else 1\n'
        'db = "/var/mobile/Media/PhotoData/Photos.sqlite"\n'
        'subprocess.run(["killall", "assetsd"], capture_output=True)\n'
        'time.sleep(1)\n'
        'rows = subprocess.run(["sqlite3", db, "SELECT Z_PK, ZDIRECTORY, ZFILENAME FROM ZASSET ORDER BY ZDATECREATED DESC LIMIT %d;" % n], capture_output=True, text=True).stdout.strip().split("\\n")\n'
        'if not rows or not rows[0]:\n'
        '    print("NO ASSETS")\n'
        '    sys.exit(0)\n'
        "triggers = subprocess.run(['sqlite3', db, \"SELECT name FROM sqlite_master WHERE type='trigger';\"], capture_output=True, text=True).stdout.strip().split('\\n')\n"
        'for t in triggers:\n'
        '    if t:\n'
        '        subprocess.run(["sqlite3", db, "DROP TRIGGER IF EXISTS %s;" % t], capture_output=True)\n'
        'for row in rows:\n'
        '    parts = row.split("|")\n'
        '    if len(parts) < 3:\n'
        '        continue\n'
        '    pk, d, f = parts[0], parts[1], parts[2]\n'
        '    path = "/var/mobile/Media/%s/%s" % (d, f)\n'
        '    subprocess.run(["sqlite3", db, "DELETE FROM ZASSET WHERE Z_PK=%s;" % pk], capture_output=True)\n'
        '    subprocess.run(["rm", "-f", path], capture_output=True)\n'
        '    print("DELETED pk=%s %s" % (pk, f))\n'
        'print("DONE %d" % len(rows))\n'
        'PYEOF\n'
        'echo DEPLOYED'
    )
    await driver.ht._call("run_command", {"command": script, "timeout": 10})


async def cleanup_all_media(driver, log=print):
    """Supprime tous les medias temporaires de l'iPhone."""
    try:
        await driver.ht._call("run_command", {
            "command": "rm -rf %s" % IPHONE_TMP,
            "timeout": 5,
        })
        log("   [media] cleanup all tmp media")
    except:
        pass
