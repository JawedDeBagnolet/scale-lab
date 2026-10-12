from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"ok": True, "ts": datetime.now(UTC).isoformat()}
