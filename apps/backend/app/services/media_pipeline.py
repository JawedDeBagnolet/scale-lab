"""Media pipeline — R2 → spoof EXIF → SCP to iPhone → Camera Roll.

Full flow for publishing media on IG/Threads:
  1. Download media from R2/CDN via the EXIF spoof server (VPS port 8502)
  2. Transfer the spoofed file to iPhone via SSH tunnel (sshpass SCP)
  3. Import into Camera Roll via MTOUCH or importmedia CLI
  4. After publication: cleanup imported media from gallery

Ported from VPS th_iphone/media.py.
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from app.services.dispatch import mcp_call, _ssh_exec, DEFAULT_MCP_PORT, DEFAULT_SSH_PORT
from app.services.mtouch import mtouch_import_media

logger = logging.getLogger("media_pipeline")

# VPS-local spoof EXIF server
SPOOF_SERVER = "http://127.0.0.1:8502"

# iPhone destination for media files
IPHONE_MEDIA_DIR = "/var/mobile/Media/th_media"

# Temp dir on VPS for downloaded/spoofed media
VPS_TMP_DIR = "/tmp/scale_media"


# ═════════════════════════════════════════════════════════════════════════════
# Step 1: Download + EXIF spoof
# ═════════════════════════════════════════════════════════════════════════════

async def download_and_spoof(
    media_url: str,
    market: str = "FR",
    device_model: str = "iPhone10,6",
    phone_id: str | None = None,
) -> str | None:
    """Download media from R2/CDN via the EXIF spoof server.

    The spoof server downloads the original, rewrites EXIF metadata
    (GPS, device model, date, software) to match the market/device,
    and returns the spoofed file.

    Args:
        media_url: Original media URL (R2 or any CDN)
        market: Country code for GPS/locale (FR, US, BR, ES, IT, GB, DE)
        device_model: iPhone model identifier (e.g. iPhone10,6)
        phone_id: Unique ID for consistent EXIF per device

    Returns:
        Local path on VPS of the spoofed file, or None on failure.
    """
    if not phone_id:
        phone_id = str(uuid.uuid4())[:8]

    # Derive extension from URL
    parsed = urlparse(media_url)
    ext = Path(parsed.path).suffix or ".jpg"
    local_path = f"{VPS_TMP_DIR}/{uuid.uuid4().hex[:12]}{ext}"

    # Ensure temp dir exists
    os.makedirs(VPS_TMP_DIR, exist_ok=True)

    # Build spoof server URL
    spoof_url = (
        f"{SPOOF_SERVER}/spoof"
        f"?url={quote(media_url, safe='')}"
        f"&market={market}"
        f"&device={quote(device_model, safe='')}"
        f"&phone_id={quote(phone_id, safe='')}"
    )

    logger.info("spoof: downloading %s → %s (market=%s)", media_url[:60], local_path, market)

    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-sL", "--max-time", "30",
            "-o", local_path,
            "-w", "%{http_code}",
            spoof_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=35)
        http_code = stdout.decode().strip()

        if proc.returncode != 0:
            logger.error("spoof: curl failed (rc=%d): %s", proc.returncode, stderr.decode()[:100])
            return None

        if http_code != "200":
            logger.error("spoof: server returned HTTP %s", http_code)
            _cleanup_file(local_path)
            return None

        # Verify file exists and has content
        if not os.path.isfile(local_path) or os.path.getsize(local_path) < 100:
            logger.error("spoof: output file missing or too small")
            _cleanup_file(local_path)
            return None

        size_kb = os.path.getsize(local_path) / 1024
        logger.info("spoof: OK — %s (%.0f KB)", local_path, size_kb)
        return local_path

    except asyncio.TimeoutError:
        logger.error("spoof: timeout downloading from spoof server")
        _cleanup_file(local_path)
        return None
    except Exception as e:
        logger.error("spoof: error — %s", e)
        _cleanup_file(local_path)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Step 2: Transfer to iPhone via SSH
# ═════════════════════════════════════════════════════════════════════════════

async def transfer_to_iphone(
    local_path: str,
    ssh_port: int = DEFAULT_SSH_PORT,
    host: str = "127.0.0.1",
) -> str | None:
    """SCP a file from VPS to the iPhone via reverse SSH tunnel.

    Uses cat + ssh pipe (more reliable than scp through tunnel).

    Args:
        local_path: Path on VPS of the file to transfer
        ssh_port: SSH tunnel port (default 2223)
        host: SSH host (default 127.0.0.1)

    Returns:
        Path on iPhone where the file was written, or None on failure.
    """
    filename = os.path.basename(local_path)
    iphone_path = f"{IPHONE_MEDIA_DIR}/{filename}"

    logger.info("transfer: %s → iPhone:%s", local_path, iphone_path)

    # Ensure destination directory exists on iPhone
    ok, _ = await _ssh_exec(
        ssh_port,
        f"mkdir -p {IPHONE_MEDIA_DIR}",
        host=host, timeout=10,
    )
    if not ok:
        logger.warning("transfer: could not create dir %s on iPhone", IPHONE_MEDIA_DIR)

    # Transfer via cat pipe through SSH (avoids SCP binary issues)
    try:
        ssh_pass = os.environ.get("IPHONE_SSH_PASS", "")
        if ssh_pass:
            ssh_cmd = [
                "sshpass", "-p", ssh_pass,
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=10",
                "-o", "PreferredAuthentications=password",
                "-o", "LogLevel=ERROR",
                "-p", str(ssh_port),
                f"root@{host}",
                f"cat > {iphone_path}",
            ]
        else:
            ssh_cmd = [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=10",
                "-o", "BatchMode=yes",
                "-o", "LogLevel=ERROR",
                "-p", str(ssh_port),
                f"root@{host}",
                f"cat > {iphone_path}",
            ]

        with open(local_path, "rb") as f:
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdin=f,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        if proc.returncode != 0:
            err = stderr.decode()[:100]
            logger.error("transfer: SSH pipe failed (rc=%d): %s", proc.returncode, err)
            return None

        # Verify file arrived
        ok, out = await _ssh_exec(
            ssh_port,
            f"stat -f '%%z' {iphone_path} 2>/dev/null || wc -c < {iphone_path}",
            host=host, timeout=10,
        )
        if ok:
            logger.info("transfer: OK — %s on iPhone (%s bytes)", iphone_path, out.strip())
        else:
            logger.warning("transfer: file sent but could not verify size")

        return iphone_path

    except asyncio.TimeoutError:
        logger.error("transfer: timeout sending to iPhone")
        return None
    except Exception as e:
        logger.error("transfer: error — %s", e)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Step 3: Import to Camera Roll
# ═════════════════════════════════════════════════════════════════════════════

async def import_to_gallery(
    iphone_path: str,
    mcp_port: int = DEFAULT_MCP_PORT,
    host: str = "127.0.0.1",
) -> bool:
    """Import a file from iPhone filesystem into the Camera Roll.

    Tries MTOUCH first (PHPhotoLibrary), then importmedia CLI as fallback.

    Args:
        iphone_path: Absolute path on iPhone (e.g. /var/mobile/Media/th_media/photo.jpg)
        mcp_port: MCP tunnel port (default 18090)
        host: MCP host

    Returns:
        True if import succeeded.
    """
    logger.info("import: %s → Camera Roll", iphone_path)

    # Method 1: MTOUCH /import (preferred — uses PHPhotoLibrary)
    result = await mtouch_import_media(iphone_path, mcp_port=mcp_port, host=host)
    if result and result.get("ok"):
        logger.info("import: OK via MTOUCH")
        return True

    logger.info("import: MTOUCH failed, trying importmedia CLI...")

    # Method 2: importmedia CLI via MCP run_command
    result = await mcp_call(
        mcp_port, "run_command",
        {"command": f"/var/jb/usr/bin/importmedia '{iphone_path}'", "timeout": 15},
        timeout=20, host=host,
    )
    if result:
        try:
            content = result.get("content", [{}])
            stdout = content[0].get("text", "") if content else ""
            if "imported" in stdout.lower() or "success" in stdout.lower() or stdout.strip():
                logger.info("import: OK via importmedia CLI — %s", stdout[:80])
                return True
        except Exception:
            pass

    logger.info("import: importmedia failed, trying PHPhotoLibrary via run_command...")

    # Method 3: Direct PHPhotoLibrary import via python/objc on iPhone
    # (last resort — uses the Photos framework directly)
    script = (
        f"python3 -c \""
        f"import objc; "
        f"from Photos import PHPhotoLibrary, PHAssetCreationRequest; "
        f"PHPhotoLibrary.sharedPhotoLibrary()"
        f".performChangesAndWait_error_("
        f"lambda: PHAssetCreationRequest.creationRequestForAssetFromImageAtFileURL_("
        f"objc.NSURL.fileURLWithPath_('{iphone_path}')), None)"
        f"\" 2>&1 || echo 'FALLBACK_FAILED'"
    )
    result = await mcp_call(
        mcp_port, "run_command",
        {"command": script, "timeout": 10},
        timeout=15, host=host,
    )
    # Even if this fails, we tried all methods
    logger.warning("import: all methods attempted for %s", iphone_path)
    return False


# ═════════════════════════════════════════════════════════════════════════════
# Step 4: Cleanup after publication
# ═════════════════════════════════════════════════════════════════════════════

async def cleanup_gallery(
    count: int = 1,
    mcp_port: int = DEFAULT_MCP_PORT,
    ssh_port: int = DEFAULT_SSH_PORT,
    host: str = "127.0.0.1",
) -> bool:
    """Delete the N most recent photos from Camera Roll after publication.

    Also removes the source file from /var/mobile/Media/th_media/.

    Args:
        count: Number of most recent photos to delete
        mcp_port: MCP port
        ssh_port: SSH port
        host: Host

    Returns:
        True if cleanup succeeded.
    """
    logger.info("cleanup: removing %d recent photo(s) from gallery", count)

    # Try GalleryService first (port 8192)
    result = await mcp_call(
        mcp_port, "run_command",
        {"command": f"curl -s -X POST http://127.0.0.1:8192/delete -H 'Content-Type: application/json' -d '{{\"count\":{count}}}'"},
        timeout=10, host=host,
    )
    if result:
        try:
            content = result.get("content", [{}])
            stdout = content[0].get("text", "") if content else ""
            if "ok" in stdout.lower() or "deleted" in stdout.lower():
                logger.info("cleanup: OK via GalleryService — %s", stdout[:80])
                return True
        except Exception:
            pass

    # Fallback: clean up the source files from th_media
    ok, _ = await _ssh_exec(
        ssh_port,
        f"rm -f {IPHONE_MEDIA_DIR}/*.jpg {IPHONE_MEDIA_DIR}/*.mp4 {IPHONE_MEDIA_DIR}/*.png 2>/dev/null; echo OK",
        host=host, timeout=10,
    )
    if ok:
        logger.info("cleanup: source files removed from %s", IPHONE_MEDIA_DIR)

    return True


async def cleanup_vps_temp(local_path: str | None = None):
    """Remove temporary media files from VPS."""
    if local_path and os.path.isfile(local_path):
        try:
            os.remove(local_path)
            logger.debug("cleanup: removed VPS temp %s", local_path)
        except OSError:
            pass


# ═════════════════════════════════════════════════════════════════════════════
# Full pipeline
# ═════════════════════════════════════════════════════════════════════════════

async def push_media(
    media_url: str,
    ssh_port: int = DEFAULT_SSH_PORT,
    mcp_port: int = DEFAULT_MCP_PORT,
    market: str = "FR",
    device_model: str = "iPhone10,6",
    phone_id: str | None = None,
    host: str = "127.0.0.1",
) -> str | None:
    """Full media pipeline: spoof → transfer → import → return iPhone path.

    Args:
        media_url: Source URL (R2, CDN, or any HTTP)
        ssh_port: SSH tunnel port to iPhone
        mcp_port: MCP tunnel port to iPhone
        market: Country code for EXIF spoofing
        device_model: iPhone model for EXIF
        phone_id: Stable phone ID for consistent EXIF
        host: Tunnel host

    Returns:
        Path on iPhone in Camera Roll if successful, None on failure.
    """
    logger.info("push_media: %s (market=%s)", media_url[:60], market)
    vps_path = None

    try:
        # Step 1: Download + spoof EXIF
        vps_path = await download_and_spoof(media_url, market, device_model, phone_id)
        if not vps_path:
            logger.error("push_media: spoof failed")
            return None

        # Step 2: Transfer to iPhone
        iphone_path = await transfer_to_iphone(vps_path, ssh_port, host)
        if not iphone_path:
            logger.error("push_media: transfer failed")
            return None

        # Step 3: Import to Camera Roll
        imported = await import_to_gallery(iphone_path, mcp_port, host)
        if not imported:
            logger.warning("push_media: gallery import failed, file is on iPhone at %s", iphone_path)
            # Return the path anyway — the publication handler can try manual selection
            return iphone_path

        logger.info("push_media: OK — %s in Camera Roll", iphone_path)
        return iphone_path

    finally:
        # Cleanup VPS temp file
        if vps_path:
            await cleanup_vps_temp(vps_path)


async def push_media_batch(
    media_urls: list[str],
    ssh_port: int = DEFAULT_SSH_PORT,
    mcp_port: int = DEFAULT_MCP_PORT,
    market: str = "FR",
    device_model: str = "iPhone10,6",
    phone_id: str | None = None,
    host: str = "127.0.0.1",
) -> list[str | None]:
    """Push multiple media files sequentially.

    Returns a list of iPhone paths (None for failed items).
    """
    results = []
    for url in media_urls:
        path = await push_media(url, ssh_port, mcp_port, market, device_model, phone_id, host)
        results.append(path)
        # Brief pause between transfers to avoid overwhelming the tunnel
        if path:
            await asyncio.sleep(0.5)
    return results


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _cleanup_file(path: str):
    """Silently remove a file."""
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
