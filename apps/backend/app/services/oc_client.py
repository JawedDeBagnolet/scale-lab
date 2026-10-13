"""OnlyChat MCP API client.

OnlyChat exposes an MCP (Model Context Protocol) server at:
  https://mcp.only-chat.ai/mcp
Auth: Authorization: Bearer oc_live_*

MCP uses JSON-RPC 2.0 over HTTP with SSE transport.
For our needs we use the Streamable HTTP transport:
  POST to the endpoint with Content-Type: application/json
  Response is JSON-RPC result.
"""

import httpx

OC_BASE = "https://mcp.only-chat.ai"
TIMEOUT = 15.0

_REQ_ID = 0


def _next_id() -> int:
    global _REQ_ID
    _REQ_ID += 1
    return _REQ_ID


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _parse_sse_response(text: str) -> dict | None:
    """Parse SSE response to extract JSON-RPC result.

    SSE format:
    event: message
    data: {"jsonrpc": "2.0", "result": {...}, "id": 1}
    """
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            import json
            try:
                return json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
    return None


async def _mcp_call(api_key: str, method: str, params: dict | None = None) -> dict:
    """Make a JSON-RPC 2.0 call to the MCP server."""
    payload: dict = {
        "jsonrpc": "2.0",
        "method": method,
        "id": _next_id(),
    }
    if params is not None:
        payload["params"] = params

    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.post(
            f"{OC_BASE}/mcp",
            headers=_headers(api_key),
            json=payload,
        )
        r.raise_for_status()

        ct = r.headers.get("content-type", "")
        if "text/event-stream" in ct:
            # SSE response
            parsed = _parse_sse_response(r.text)
            if parsed:
                return parsed
            raise ValueError("Could not parse SSE response")
        else:
            # Direct JSON response
            return r.json()


async def test_connection(api_key: str) -> dict:
    """Test the API key by listing available tools.

    Returns {"ok": True, "tools": [...]} or {"ok": False, "error": "..."}.
    """
    try:
        result = await _mcp_call(api_key, "tools/list")

        if "error" in result:
            err = result["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            return {"ok": False, "error": msg}

        tools = result.get("result", {}).get("tools", [])
        return {"ok": True, "tool_count": len(tools)}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return {"ok": False, "error": "Cle API invalide"}
        if e.response.status_code == 403:
            return {"ok": False, "error": "Acces refuse"}
        return {"ok": False, "error": f"Erreur HTTP {e.response.status_code}"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Timeout - serveur OC injoignable"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def _call_tool(api_key: str, tool_name: str, arguments: dict | None = None) -> dict:
    """Call an MCP tool and return its result."""
    params: dict = {"name": tool_name}
    if arguments:
        params["arguments"] = arguments

    result = await _mcp_call(api_key, "tools/call", params)

    if "error" in result:
        err = result["error"]
        raise ValueError(err.get("message", str(err)) if isinstance(err, dict) else str(err))

    return result.get("result", {})


async def get_status(api_key: str) -> dict:
    """Get account status: creators, balance, etc."""
    try:
        # First verify connection
        test = await test_connection(api_key)
        if not test["ok"]:
            return test

        status: dict = {"ok": True}

        # Try to list creators
        try:
            creators_result = await _call_tool(api_key, "list_creators")
            content = creators_result.get("content", [])
            # MCP tool results have content as array of {type, text} blocks
            if content and isinstance(content, list):
                import json
                for block in content:
                    if block.get("type") == "text":
                        try:
                            data = json.loads(block["text"])
                            if isinstance(data, list):
                                status["creator_count"] = len(data)
                                status["creators"] = [
                                    {
                                        "id": c.get("id"),
                                        "name": c.get("name") or c.get("display_name"),
                                    }
                                    for c in data[:20]  # Cap at 20
                                ]
                            elif isinstance(data, dict):
                                items = data.get("creators") or data.get("data") or data.get("items") or []
                                status["creator_count"] = len(items)
                        except json.JSONDecodeError:
                            pass
        except Exception:
            # Tool might not exist or might fail; that's OK
            status["creator_count"] = None

        # Try to get organization info
        try:
            org_result = await _call_tool(api_key, "get_organization")
            content = org_result.get("content", [])
            if content and isinstance(content, list):
                import json
                for block in content:
                    if block.get("type") == "text":
                        try:
                            data = json.loads(block["text"])
                            status["org_name"] = data.get("name")
                            status["balance"] = data.get("balance") or data.get("credits")
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass

        return status
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def list_creators(api_key: str) -> list:
    """List all creators in the organization."""
    result = await _call_tool(api_key, "list_creators")
    content = result.get("content", [])
    import json
    for block in content:
        if block.get("type") == "text":
            try:
                data = json.loads(block["text"])
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("creators") or data.get("data") or data.get("items") or []
            except json.JSONDecodeError:
                continue
    return []


async def get_creator_stats(api_key: str, creator_id: str) -> dict:
    """Get stats for a specific creator."""
    result = await _call_tool(api_key, "get_creator_stats", {"creator_id": creator_id})
    content = result.get("content", [])
    import json
    for block in content:
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                continue
    return {}


async def list_scripts(api_key: str, creator_id: str) -> list:
    """List scripts for a creator."""
    result = await _call_tool(api_key, "list_scripts", {"creator_id": creator_id})
    content = result.get("content", [])
    import json
    for block in content:
        if block.get("type") == "text":
            try:
                data = json.loads(block["text"])
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("scripts") or data.get("data") or data.get("items") or []
            except json.JSONDecodeError:
                continue
    return []


async def list_fans(api_key: str, creator_id: str, limit: int = 50) -> list:
    """List fans for a creator."""
    result = await _call_tool(
        api_key, "list_fans", {"creator_id": creator_id, "limit": limit}
    )
    content = result.get("content", [])
    import json
    for block in content:
        if block.get("type") == "text":
            try:
                data = json.loads(block["text"])
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("fans") or data.get("data") or data.get("items") or []
            except json.JSONDecodeError:
                continue
    return []
