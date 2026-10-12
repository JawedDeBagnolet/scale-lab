"""WebSocket hub — broadcast events to connected clients."""

import asyncio
import json
from datetime import UTC, datetime

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Simple broadcast hub for live log events."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.remove(ws)

    async def broadcast(self, data: dict) -> None:
        payload = json.dumps(data, default=str)
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.remove(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


async def ws_logs(ws: WebSocket) -> None:
    """WebSocket endpoint: streams log events to the client."""
    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive; client can send pings
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text(
                    json.dumps({"type": "pong", "ts": datetime.now(UTC).isoformat()})
                )
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)
