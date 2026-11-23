"""Generate R2 thumbnails for media that don't have one.

Downloads original from R2, resizes to 300×375 JPEG, uploads back to R2
via the gateway, and updates the DB record with the thumbnail URL.
"""

import asyncio
import io
import logging
import os
from urllib.parse import urlparse

import httpx
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.posting import Media

logger = logging.getLogger("thumb_generator")

GATEWAY_BASE = os.environ.get("GATEWAY_URL", "https://api.scalelab.win")
API_SECRET = os.environ.get("API_SECRET", "")

THUMB_W = 300
THUMB_H = 375
JPEG_QUALITY = 60


async def _download_image(url: str) -> bytes | None:
    """Download image bytes from R2/gateway (with auth + referer)."""
    try:
        headers = {
            "Referer": "https://scalelab.win/",
            "Origin": "https://scalelab.win",
        }
        if API_SECRET:
            headers["Authorization"] = f"Bearer {API_SECRET}"
        async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                return r.content
            logger.warning("download %s → HTTP %d body=%s", url[:60], r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("download error %s: %s", url[:60], e)
    return None


def _resize_to_thumb(data: bytes) -> bytes | None:
    """Resize image to THUMB_W×THUMB_H cover crop, return JPEG bytes."""
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")

        # Cover crop: scale so the smallest dimension matches, then center crop
        iw, ih = img.size
        scale = max(THUMB_W / iw, THUMB_H / ih)
        new_w, new_h = int(iw * scale), int(ih * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center crop
        left = (new_w - THUMB_W) // 2
        top = (new_h - THUMB_H) // 2
        img = img.crop((left, top, left + THUMB_W, top + THUMB_H))

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue()
    except Exception as e:
        logger.warning("resize error: %s", e)
        return None


async def _upload_thumb(thumb_bytes: bytes, filename: str, persona_id: str | None) -> str | None:
    """Upload thumbnail JPEG to R2 via the gateway."""
    try:
        files = {"file": (filename, thumb_bytes, "image/jpeg")}
        data = {}
        if persona_id:
            data["persona_id"] = str(persona_id)

        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            r = await client.post(
                f"{GATEWAY_BASE}/api/upload/media",
                headers={"Authorization": f"Bearer {API_SECRET}"},
                files=files,
                data=data,
            )
            if r.status_code in (200, 201):
                result = r.json()
                return result.get("url")
            logger.warning("upload thumb → HTTP %d: %s", r.status_code, r.text[:100])
    except Exception as e:
        logger.warning("upload thumb error: %s", e)
    return None


async def generate_missing_thumbnails(db: AsyncSession) -> dict:
    """Find all image medias without thumbnail and generate them.

    Returns stats: {total, generated, skipped, errors}.
    """
    # Find image medias without thumbnail
    stmt = select(Media).where(
        Media.media_type == "image",
        Media.thumbnail_url.is_(None),
        Media.url.isnot(None),
    )
    result = await db.execute(stmt)
    medias = list(result.scalars().all())

    stats = {"total": len(medias), "generated": 0, "skipped": 0, "errors": 0}
    logger.info("thumb_generator: %d images without thumbnails", len(medias))

    for m in medias:
        try:
            # Download original
            data = await _download_image(m.url)
            if not data:
                stats["errors"] += 1
                continue

            # Skip if too small (probably already a thumbnail)
            if len(data) < 5000:
                stats["skipped"] += 1
                continue

            # Resize
            thumb_bytes = _resize_to_thumb(data)
            if not thumb_bytes:
                stats["errors"] += 1
                continue

            # Upload
            parsed = urlparse(m.url)
            orig_name = os.path.basename(parsed.path)
            thumb_name = orig_name.rsplit(".", 1)[0] + "_thumb.jpg"

            thumb_url = await _upload_thumb(
                thumb_bytes, thumb_name, str(m.persona_id) if m.persona_id else None
            )
            if not thumb_url:
                stats["errors"] += 1
                continue

            # Update DB
            m.thumbnail_url = thumb_url
            await db.commit()
            stats["generated"] += 1
            logger.info("thumb OK: %s → %s", m.url[:50], thumb_url[:50])

            # Brief pause to avoid overwhelming gateway
            await asyncio.sleep(0.2)

        except Exception as e:
            stats["errors"] += 1
            logger.warning("thumb error for media %s: %s", m.id, e)

    logger.info("thumb_generator done: %s", stats)
    return stats
