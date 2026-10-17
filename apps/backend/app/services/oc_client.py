"""OnlyChat MCP API client.

OnlyChat exposes an MCP (Model Context Protocol) server at:
  https://mcp.only-chat.ai/mcp
Auth: Authorization: Bearer oc_live_*

MCP Streamable HTTP transport requires:
  1. POST initialize → get Mcp-Session-Id
  2. POST notifications/initialized
  3. Then tools/list, tools/call, etc.
All subsequent requests carry Mcp-Session-Id + MCP-Protocol-Version.
"""

import json
import logging

import httpx

logger = logging.getLogger("scalelab.oc")

OC_MCP_URL = "https://mcp.only-chat.ai/mcp"
TIMEOUT = 20.0
MCP_PROTOCOL_VERSION = "2025-03-26"

_REQ_ID = 0


def _next_id() -> int:
    global _REQ_ID
    _REQ_ID += 1
    return _REQ_ID


# ── SSE parsing ────────────────────────────────────────────

def _parse_sse(text: str) -> dict | None:
    """Parse an SSE response body and return the last JSON-RPC message."""
    result = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                continue
    return result


def _extract(r: httpx.Response) -> dict:
    """Extract JSON-RPC result from either JSON or SSE response."""
    ct = r.headers.get("content-type", "")
    if "text/event-stream" in ct:
        parsed = _parse_sse(r.text)
        if parsed:
            return parsed
        raise ValueError(f"Could not parse SSE response: {r.text[:300]}")
    return r.json()


# ── MCP Session ────────────────────────────────────────────

class MCPSession:
    """One initialised session against the OC MCP server."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session_id: str | None = None
        self.version: str = MCP_PROTOCOL_VERSION
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        self._tools: list | None = None

    # ── headers ──

    def _base_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _headers(self) -> dict:
        h = self._base_headers()
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        h["MCP-Protocol-Version"] = self.version
        return h

    # ── lifecycle ──

    async def initialize(self) -> dict:
        """MCP initialize handshake (required before any tool call)."""
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": _next_id(),
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ScaleLab", "version": "1.0.0"},
            },
        }
        logger.info("MCP initialize → %s", OC_MCP_URL)
        r = await self.client.post(
            OC_MCP_URL,
            headers=self._base_headers(),
            json=payload,
        )
        logger.info("MCP initialize ← %s  ct=%s", r.status_code, r.headers.get("content-type", "?"))
        r.raise_for_status()
        result = _extract(r)

        # Store session id
        sid = r.headers.get("mcp-session-id")
        if sid:
            self.session_id = sid
            logger.info("MCP session id: %s", sid[:16] + "...")

        # Negotiated version
        sv = (result.get("result") or {}).get("protocolVersion")
        if sv:
            self.version = sv

        # Send initialized notification
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        try:
            nr = await self.client.post(
                OC_MCP_URL, headers=self._headers(), json=notif,
            )
            logger.info("MCP initialized notification ← %s", nr.status_code)
        except Exception as e:
            logger.warning("MCP initialized notification failed (non-fatal): %s", e)

        return result

    async def close(self):
        """Clean up the HTTP client."""
        try:
            await self.client.aclose()
        except Exception:
            pass

    # ── JSON-RPC ──

    async def _call(self, method: str, params: dict | None = None) -> dict:
        payload: dict = {
            "jsonrpc": "2.0",
            "method": method,
            "id": _next_id(),
        }
        if params is not None:
            payload["params"] = params

        r = await self.client.post(
            OC_MCP_URL, headers=self._headers(), json=payload,
        )
        r.raise_for_status()
        return _extract(r)

    async def list_tools(self) -> list:
        """tools/list — returns the tool descriptors."""
        if self._tools is not None:
            return self._tools
        result = await self._call("tools/list")
        if "error" in result:
            err = result["error"]
            raise ValueError(err.get("message", str(err)) if isinstance(err, dict) else str(err))
        self._tools = result.get("result", {}).get("tools", [])
        logger.info("MCP tools/list → %d tools: %s",
                     len(self._tools),
                     [t.get("name") for t in self._tools])
        return self._tools

    async def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """tools/call — invoke a tool by name."""
        params: dict = {"name": name, "arguments": arguments or {}}

        logger.info("MCP tools/call → %s(%s)", name, arguments or {})
        result = await self._call("tools/call", params)

        if "error" in result:
            err = result["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            logger.warning("MCP tools/call %s error: %s", name, msg)
            raise ValueError(msg)

        return result.get("result", {})


async def _open(api_key: str) -> MCPSession:
    """Open + initialize a session. Caller must close()."""
    s = MCPSession(api_key)
    await s.initialize()
    return s


# ── Helper: extract text content from MCP tool result ──────

def _text_content(result: dict) -> str | None:
    """Return the first text block from an MCP tool result."""
    content = result.get("content", [])
    if not content or not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            return block.get("text")
    return None


def _json_content(result: dict) -> any:
    """Parse the first text block as JSON."""
    text = _text_content(result)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ── Public API (same interface as before) ──────────────────

async def test_connection(api_key: str) -> dict:
    """Test the API key by doing the full MCP handshake + tools/list.

    Returns {"ok": True, "tool_count": N, "tools": [...]} or {"ok": False, "error": "..."}.
    """
    session = MCPSession(api_key)
    try:
        await session.initialize()
        tools = await session.list_tools()
        tool_names = [t.get("name", "?") for t in tools]
        logger.info("OC test OK — %d tools: %s", len(tools), tool_names)
        return {"ok": True, "tool_count": len(tools), "tools": tool_names}
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text[:300]
        except Exception:
            pass
        logger.warning("OC test HTTP %s: %s", e.response.status_code, body)
        if e.response.status_code == 401:
            return {"ok": False, "error": "Cle API invalide ou header Authorization incorrect"}
        if e.response.status_code == 403:
            return {"ok": False, "error": "Acces refuse"}
        return {"ok": False, "error": f"Erreur HTTP {e.response.status_code}: {body[:100]}"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Timeout - serveur OC injoignable"}
    except Exception as e:
        logger.exception("OC test error")
        return {"ok": False, "error": str(e)[:200]}
    finally:
        await session.close()


async def get_status(api_key: str) -> dict:
    """Get account status: creators, balance, etc. via one MCP session."""
    session = MCPSession(api_key)
    try:
        await session.initialize()
        tools = await session.list_tools()
        tool_names = [t.get("name", "?") for t in tools]
        status: dict = {"ok": True, "tool_count": len(tools)}

        # List creators
        try:
            data = _json_content(await session.call_tool("list_creators"))
            if isinstance(data, list):
                status["creator_count"] = len(data)
                status["creators"] = [
                    {"id": c.get("id"), "name": c.get("name") or c.get("display_name")}
                    for c in data[:20]
                ]
            elif isinstance(data, dict):
                items = data.get("creators") or data.get("data") or data.get("items") or []
                status["creator_count"] = len(items)
                status["creators"] = [
                    {"id": c.get("id"), "name": c.get("name") or c.get("display_name")}
                    for c in items[:20]
                ]
        except Exception as e:
            logger.warning("OC list_creators in get_status: %s", e)
            status["creator_count"] = None

        # Organization info (balance, etc.)
        try:
            data = _json_content(await session.call_tool("get_organization"))
            if isinstance(data, dict):
                status["org_name"] = data.get("name")
                status["balance"] = data.get("balance") or data.get("credits")
        except Exception as e:
            logger.warning("OC get_organization in get_status: %s", e)

        return status
    except Exception as e:
        logger.exception("OC get_status error")
        return {"ok": False, "error": str(e)[:200]}
    finally:
        await session.close()


async def list_creators(api_key: str) -> list:
    """List all creators in the organization."""
    session = MCPSession(api_key)
    try:
        await session.initialize()
        data = _json_content(await session.call_tool("list_creators"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("creators") or data.get("data") or data.get("items") or []
        return []
    except Exception as e:
        logger.exception("OC list_creators error")
        return []
    finally:
        await session.close()


async def get_creator_stats(api_key: str, creator_id: str) -> dict:
    """Get stats for a specific creator."""
    session = MCPSession(api_key)
    try:
        await session.initialize()
        # OC tool name is "get_stats", not "get_creator_stats"
        data = _json_content(await session.call_tool("get_stats", {"creator_id": creator_id}))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.exception("OC get_stats error")
        return {}
    finally:
        await session.close()


async def list_transactions(api_key: str, creator_id: str, limit: int = 50) -> list:
    """List transactions for a creator."""
    session = MCPSession(api_key)
    try:
        await session.initialize()
        data = _json_content(await session.call_tool(
            "list_transactions", {"creator_id": creator_id, "limit": limit}
        ))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("transactions") or data.get("data") or data.get("items") or []
        return []
    except Exception as e:
        logger.exception("OC list_transactions error")
        return []
    finally:
        await session.close()


async def list_scripts(api_key: str, creator_id: str) -> list:
    """List scripts for a creator."""
    session = MCPSession(api_key)
    try:
        await session.initialize()
        data = _json_content(await session.call_tool("list_scripts", {"creator_id": creator_id}))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("scripts") or data.get("data") or data.get("items") or []
        return []
    except Exception as e:
        logger.exception("OC list_scripts error")
        return []
    finally:
        await session.close()


async def list_fans(api_key: str, creator_id: str, limit: int = 50) -> list:
    """List fans for a creator."""
    session = MCPSession(api_key)
    try:
        await session.initialize()
        data = _json_content(await session.call_tool(
            "list_fans", {"creator_id": creator_id, "limit": limit}
        ))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("fans") or data.get("data") or data.get("items") or []
        return []
    except Exception as e:
        logger.exception("OC list_fans error")
        return []
    finally:
        await session.close()
