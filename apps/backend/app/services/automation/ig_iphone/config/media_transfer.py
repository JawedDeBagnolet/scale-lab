"""
ig_iphone/config/media_transfer.py — Transfert de medias vers l'iPhone.

Pipeline :
  1. Upload via ios-mcp /upload_file (tunnel VPS → iPhone)
  2. Import galerie via mtouch /import

Ported from VPS — adapted to async (httpx).
"""

import asyncio
import os
from typing import Any, Callable

import httpx


async def import_media(local_path: str, mcp_port: int = 8190, gallery_port: int = 8191,
                       log: Callable = print) -> dict | None:
    """Importe un fichier media local dans la galerie iOS.

    Args:
        local_path: chemin du fichier sur le VPS
        mcp_port: port du tunnel MCP (defaut: 8190)
        gallery_port: port du service gallery (defaut: 8191)
        log: fonction de log
    Returns:
        dict avec ok, path, type ou None si echec
    """
    if not os.path.exists(local_path):
        log("   ! fichier non trouve: %s" % local_path)
        return None

    filename = os.path.basename(local_path)
    log("-> Media: import '%s'" % filename)

    # 1. Upload vers l'iPhone via ios-mcp /upload_file
    try:
        upload_url = "http://127.0.0.1:%d/upload_file" % mcp_port
        with open(local_path, "rb") as f:
            data = f.read()

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                upload_url,
                content=data,
                headers={"X-Filename": filename},
            )
            upload_data = r.json()

        remote_path = upload_data.get("path") or upload_data.get("filePath")
        if not remote_path:
            log("   ! upload pas de path retourne: %s" % str(upload_data)[:200])
            return None
        log("   upload OK -> %s" % remote_path)
    except Exception as e:
        log("   ! upload erreur: %s" % str(e)[:100])
        return None

    # 2. Import dans la galerie via mtouch
    try:
        gallery_url = "http://127.0.0.1:%d/import" % gallery_port
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(gallery_url, json={"path": remote_path})
            result = resp.json()

        if result.get("ok"):
            log("   import galerie OK (%s)" % result.get("type", "?"))
            return result
        else:
            log("   ! import galerie: %s" % result.get("error", "?"))
            return None
    except Exception as e:
        log("   ! import erreur: %s" % str(e)[:100])
        return None


async def import_media_batch(local_paths: list[str], mcp_port: int = 8190,
                             gallery_port: int = 8191, delay: float = 2,
                             log: Callable = print) -> list:
    """Importe plusieurs fichiers dans la galerie iOS."""
    results = []
    for i, path in enumerate(local_paths):
        r = await import_media(path, mcp_port=mcp_port, gallery_port=gallery_port, log=log)
        results.append(r)
        if i < len(local_paths) - 1:
            await asyncio.sleep(delay)
    ok = sum(1 for r in results if r)
    log("   batch: %d/%d importes" % (ok, len(local_paths)))
    return results
