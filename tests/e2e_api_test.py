#!/usr/bin/env python3
"""
Scale Lab — E2E API Test Suite
Tests every module's CRUD endpoints against the live API.

Usage:
    python tests/e2e_api_test.py [--base-url URL] [--token TOKEN]

By default hits https://api.scalelab.win/api with the configured token.
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, UTC
from typing import Any

import httpx

# ── Config ───────────────────────────────────────────────────────
DEFAULT_BASE = "https://api.scalelab.win"
DEFAULT_TOKEN = "75640332d36f253e8debecbcc6dba4d0eebfd9fafaeac96812b67593d77886b7"

# Track test results
results: list[dict] = []
created_ids: dict[str, Any] = {}  # module -> id (for cleanup)


def api(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json_data: dict | None = None,
    params: dict | None = None,
    expect: int | list[int] = 200,
) -> dict | list | None:
    """Make an API call and return the response JSON."""
    if isinstance(expect, int):
        expect = [expect]
    try:
        resp = client.request(method, path, json=json_data, params=params, timeout=30)
        if resp.status_code in expect:
            try:
                return resp.json()
            except Exception:
                return None
        else:
            return {"_error": True, "_status": resp.status_code, "_body": resp.text[:500]}
    except Exception as e:
        return {"_error": True, "_status": 0, "_body": str(e)}


def test(module: str, name: str, passed: bool, detail: str = ""):
    """Record a test result."""
    status = "PASS" if passed else "FAIL"
    emoji = "✅" if passed else "❌"
    results.append({"module": module, "name": name, "passed": passed, "detail": detail})
    print(f"  {emoji} {module} / {name}" + (f" — {detail}" if detail and not passed else ""))


def is_ok(resp: Any) -> bool:
    """Check if response is valid (not an error)."""
    if resp is None:
        return False
    if isinstance(resp, dict) and resp.get("_error"):
        return False
    return True


def is_list(resp: Any) -> bool:
    """Check if response is a non-error list or dict with data."""
    if isinstance(resp, list):
        return True
    if isinstance(resp, dict) and not resp.get("_error"):
        return True
    return False


# ── Module Tests ─────────────────────────────────────────────────


def test_health(c: httpx.Client):
    """Health check endpoint."""
    r = api(c, "GET", "/health")
    test("health", "GET /health", is_ok(r))


def test_dashboard(c: httpx.Client):
    """Dashboard stats and layout."""
    r = api(c, "GET", "/api/dashboard/stats")
    test("dashboard", "GET /stats", is_ok(r))

    r = api(c, "GET", "/api/dashboard/layout")
    test("dashboard", "GET /layout", is_ok(r))


def test_personas(c: httpx.Client):
    """Personas CRUD."""
    # List
    r = api(c, "GET", "/api/personas")
    test("personas", "GET /personas (list)", isinstance(r, list))

    # Create
    data = {
        "nom": f"E2E Test Persona {uuid.uuid4().hex[:6]}",
        "couleur": "#ff5500",
        "bio": "Test persona for E2E",
    }
    r = api(c, "POST", "/api/personas", json_data=data, expect=[200, 201])
    ok = is_ok(r) and isinstance(r, dict) and "id" in r
    test("personas", "POST /personas (create)", ok)
    if ok:
        created_ids["persona"] = r["id"]

    # Get one
    if "persona" in created_ids:
        r = api(c, "GET", f"/api/personas/{created_ids['persona']}")
        test("personas", "GET /personas/:id", is_ok(r))

    # Update
    if "persona" in created_ids:
        r = api(c, "PATCH", f"/api/personas/{created_ids['persona']}", json_data={"bio": "Updated E2E"})
        test("personas", "PATCH /personas/:id", is_ok(r))

    # Delete (cleanup)
    if "persona" in created_ids:
        r = api(c, "DELETE", f"/api/personas/{created_ids['persona']}", expect=[200, 204])
        test("personas", "DELETE /personas/:id", r is None or not (isinstance(r, dict) and r.get("_error")))
        del created_ids["persona"]


def test_comptes(c: httpx.Client):
    """Comptes CRUD — needs a persona."""
    # List
    r = api(c, "GET", "/api/comptes")
    test("comptes", "GET /comptes (list)", isinstance(r, list))

    # Create needs persona_id — use first existing persona
    personas = api(c, "GET", "/api/personas")
    if isinstance(personas, list) and len(personas) > 0:
        pid = personas[0]["id"]
        data = {
            "persona_id": pid,
            "plateforme": "ig",
            "username": f"e2e_test_{uuid.uuid4().hex[:6]}",
            "statut": "ok",
        }
        r = api(c, "POST", "/api/comptes", json_data=data, expect=[200, 201])
        ok = is_ok(r) and isinstance(r, dict) and "id" in r
        test("comptes", "POST /comptes (create)", ok)
        if ok:
            created_ids["compte"] = r["id"]
            # Get
            r2 = api(c, "GET", f"/api/comptes/{r['id']}")
            test("comptes", "GET /comptes/:id", is_ok(r2))
            # Patch
            r3 = api(c, "PATCH", f"/api/comptes/{r['id']}", json_data={"statut": "checkpoint"})
            test("comptes", "PATCH /comptes/:id", is_ok(r3))
            # Delete
            r4 = api(c, "DELETE", f"/api/comptes/{r['id']}", expect=[200, 204])
            test("comptes", "DELETE /comptes/:id", r4 is None or not (isinstance(r4, dict) and r4.get("_error")))
            del created_ids["compte"]
    else:
        test("comptes", "POST /comptes (create)", False, "no persona available")


def test_targets(c: httpx.Client):
    """Targets CRUD."""
    r = api(c, "GET", "/api/targets")
    test("targets", "GET /targets (list)", isinstance(r, list))

    data = {
        "username": f"e2e_target_{uuid.uuid4().hex[:6]}",
        "plateforme": "ig",
    }
    r = api(c, "POST", "/api/targets", json_data=data, expect=[200, 201])
    ok = is_ok(r) and isinstance(r, dict) and "id" in r
    test("targets", "POST /targets (create)", ok)
    if ok:
        tid = r["id"]
        r2 = api(c, "PATCH", f"/api/targets/{tid}", json_data={"priorite": 5})
        test("targets", "PATCH /targets/:id", is_ok(r2))
        r3 = api(c, "DELETE", f"/api/targets/{tid}", expect=[200, 204])
        test("targets", "DELETE /targets/:id", r3 is None or not (isinstance(r3, dict) and r3.get("_error")))


def test_presets(c: httpx.Client):
    """Comportements (presets) CRUD."""
    r = api(c, "GET", "/api/presets")
    test("presets", "GET /presets (list)", isinstance(r, list))

    data = {
        "nom": f"E2E Preset {uuid.uuid4().hex[:6]}",
        "plateforme": "ig",
        "type_session": "feed",
        "params": {"like": 0.5, "follow": 0.1},
    }
    r = api(c, "POST", "/api/presets", json_data=data, expect=[200, 201])
    ok = is_ok(r) and isinstance(r, dict) and "id" in r
    test("presets", "POST /presets (create)", ok)
    if ok:
        pid = r["id"]
        r2 = api(c, "PATCH", f"/api/presets/{pid}", json_data={"nom": "E2E Updated"})
        test("presets", "PATCH /presets/:id", is_ok(r2))
        r3 = api(c, "DELETE", f"/api/presets/{pid}", expect=[200, 204])
        test("presets", "DELETE /presets/:id", r3 is None or not (isinstance(r3, dict) and r3.get("_error")))


def test_settings(c: httpx.Client):
    """Settings read/update."""
    r = api(c, "GET", "/api/settings")
    test("settings", "GET /settings", is_ok(r))

    # Update (just re-save current notifications field)
    if isinstance(r, dict):
        r2 = api(c, "PATCH", "/api/settings", json_data={"notifications": r.get("notifications", {})})
        test("settings", "PATCH /settings", is_ok(r2))


def test_logs(c: httpx.Client):
    """Logs: events, incidents, alert rules."""
    r = api(c, "GET", "/api/logs/events")
    test("logs", "GET /events (list)", isinstance(r, list))

    r = api(c, "GET", "/api/logs/incidents")
    test("logs", "GET /incidents (list)", isinstance(r, list))

    r = api(c, "GET", "/api/logs/rules")
    test("logs", "GET /rules (list)", isinstance(r, list))

    r = api(c, "GET", "/api/logs/stats")
    test("logs", "GET /stats", is_ok(r))

    # Create an event
    data = {
        "module": "e2e_test",
        "event_type": "test_run",
        "level": "info",
        "message": "E2E test event",
    }
    r = api(c, "POST", "/api/logs/events", json_data=data, expect=[200, 201])
    test("logs", "POST /events (create)", is_ok(r))


def test_proxies(c: httpx.Client):
    """Proxies CRUD."""
    r = api(c, "GET", "/api/proxies")
    test("proxies", "GET /proxies (list)", isinstance(r, list))

    data = {
        "nom": f"E2E Proxy {uuid.uuid4().hex[:6]}",
        "host": "127.0.0.1",
        "port": 8080,
        "type_proxy": "http",
    }
    r = api(c, "POST", "/api/proxies", json_data=data, expect=[200, 201])
    ok = is_ok(r) and isinstance(r, dict) and "id" in r
    test("proxies", "POST /proxies (create)", ok)
    if ok:
        pid = r["id"]
        r2 = api(c, "PATCH", f"/api/proxies/{pid}", json_data={"nom": "E2E Updated Proxy"})
        test("proxies", "PATCH /proxies/:id", is_ok(r2))
        r3 = api(c, "DELETE", f"/api/proxies/{pid}", expect=[200, 204])
        test("proxies", "DELETE /proxies/:id", r3 is None or not (isinstance(r3, dict) and r3.get("_error")))


def test_iphones(c: httpx.Client):
    """iPhones CRUD."""
    r = api(c, "GET", "/api/iphones")
    test("iphones", "GET /iphones (list)", isinstance(r, list))

    data = {
        "nom": f"E2E iPhone {uuid.uuid4().hex[:6]}",
        "udid": uuid.uuid4().hex[:16],
        "modele": "iPhone 15",
    }
    r = api(c, "POST", "/api/iphones", json_data=data, expect=[200, 201])
    ok = is_ok(r) and isinstance(r, dict) and "id" in r
    test("iphones", "POST /iphones (create)", ok)
    if ok:
        iid = r["id"]
        r2 = api(c, "PATCH", f"/api/iphones/{iid}", json_data={"nom": "E2E Updated iPhone"})
        test("iphones", "PATCH /iphones/:id", is_ok(r2))
        r3 = api(c, "DELETE", f"/api/iphones/{iid}", expect=[200, 204])
        test("iphones", "DELETE /iphones/:id", r3 is None or not (isinstance(r3, dict) and r3.get("_error")))


def test_statistiques(c: httpx.Client):
    """Stats endpoints."""
    r = api(c, "GET", "/api/stats")
    test("stats", "GET /stats (list)", isinstance(r, list) or is_ok(r))

    r = api(c, "GET", "/api/stats/overview")
    test("stats", "GET /stats/overview", is_ok(r))


def test_veille(c: httpx.Client):
    """Veille CRUD — sources, inspirations, favorites, snipes, albums."""
    r = api(c, "GET", "/api/veille/sources")
    test("veille", "GET /sources (list)", isinstance(r, list))

    r = api(c, "GET", "/api/veille/inspirations")
    test("veille", "GET /inspirations (list)", isinstance(r, list))

    r = api(c, "GET", "/api/veille/favorites")
    test("veille", "GET /favorites (list)", isinstance(r, list))

    r = api(c, "GET", "/api/veille/snipes")
    test("veille", "GET /snipes (list)", isinstance(r, list))

    r = api(c, "GET", "/api/veille/albums")
    test("veille", "GET /albums (list)", isinstance(r, list))

    # Create a source
    data = {
        "nom": f"E2E Source {uuid.uuid4().hex[:6]}",
        "plateforme": "ig",
        "username": f"e2e_source_{uuid.uuid4().hex[:6]}",
    }
    r = api(c, "POST", "/api/veille/sources", json_data=data, expect=[200, 201])
    ok = is_ok(r) and isinstance(r, dict) and "id" in r
    test("veille", "POST /sources (create)", ok)
    if ok:
        sid = r["id"]
        r2 = api(c, "DELETE", f"/api/veille/sources/{sid}", expect=[200, 204])
        test("veille", "DELETE /sources/:id", r2 is None or not (isinstance(r2, dict) and r2.get("_error")))


def test_crm(c: httpx.Client):
    """CRM endpoints — fans, transactions, scripts, overview."""
    r = api(c, "GET", "/api/crm/fans")
    test("crm", "GET /fans (list)", isinstance(r, list))

    r = api(c, "GET", "/api/crm/transactions")
    test("crm", "GET /transactions (list)", isinstance(r, list))

    r = api(c, "GET", "/api/crm/scripts")
    test("crm", "GET /scripts (list)", isinstance(r, list))

    r = api(c, "GET", "/api/crm/overview")
    test("crm", "GET /overview", is_ok(r))


def test_posting(c: httpx.Client):
    """Posting — medias, templates, collections, campaigns, publications."""
    r = api(c, "GET", "/api/posting/medias")
    test("posting", "GET /medias (list)", isinstance(r, list))

    r = api(c, "GET", "/api/posting/templates")
    test("posting", "GET /templates (list)", isinstance(r, list))

    r = api(c, "GET", "/api/posting/collections")
    test("posting", "GET /collections (list)", isinstance(r, list))

    r = api(c, "GET", "/api/posting/campagnes")
    test("posting", "GET /campagnes (list)", isinstance(r, list))

    r = api(c, "GET", "/api/posting/publications")
    test("posting", "GET /publications (list)", isinstance(r, list))

    r = api(c, "GET", "/api/posting/overview")
    test("posting", "GET /overview", is_ok(r))

    # Create a collection
    data = {
        "nom": f"E2E Collection {uuid.uuid4().hex[:6]}",
    }
    r = api(c, "POST", "/api/posting/collections", json_data=data, expect=[200, 201])
    ok = is_ok(r) and isinstance(r, dict) and "id" in r
    test("posting", "POST /collections (create)", ok)
    if ok:
        cid = r["id"]
        r2 = api(c, "DELETE", f"/api/posting/collections/{cid}", expect=[200, 204])
        test("posting", "DELETE /collections/:id", r2 is None or not (isinstance(r2, dict) and r2.get("_error")))


def test_liens(c: httpx.Client):
    """Liens — tracked links, domains."""
    r = api(c, "GET", "/api/liens")
    test("liens", "GET /liens (list)", isinstance(r, list))

    r = api(c, "GET", "/api/liens/domains")
    test("liens", "GET /domains (list)", isinstance(r, list))

    # Create a tracked link
    data = {
        "slug": f"e2e-{uuid.uuid4().hex[:6]}",
        "destination": "https://example.com/test",
        "link_type": "direct",
        "plateforme": "ig",
    }
    r = api(c, "POST", "/api/liens", json_data=data, expect=[200, 201])
    ok = is_ok(r) and isinstance(r, dict) and "id" in r
    test("liens", "POST /liens (create)", ok)
    if ok:
        lid = r["id"]
        r2 = api(c, "DELETE", f"/api/liens/{lid}", expect=[200, 204])
        test("liens", "DELETE /liens/:id", r2 is None or not (isinstance(r2, dict) and r2.get("_error")))


def test_scenarios(c: httpx.Client):
    """Scenarios CRUD + plages + runs."""
    r = api(c, "GET", "/api/scenarios")
    test("scenarios", "GET /scenarios (list)", isinstance(r, list))

    r = api(c, "GET", "/api/scenarios/plages")
    test("scenarios", "GET /plages (list)", isinstance(r, list))

    r = api(c, "GET", "/api/scenarios/runs/list")
    test("scenarios", "GET /runs/list", isinstance(r, list))

    # Create a scenario
    data = {
        "nom": f"E2E Scenario {uuid.uuid4().hex[:6]}",
        "plateforme": "ig",
        "type_session": "feed",
        "steps": [],
    }
    r = api(c, "POST", "/api/scenarios", json_data=data, expect=[200, 201])
    ok = is_ok(r) and isinstance(r, dict) and "id" in r
    test("scenarios", "POST /scenarios (create)", ok)
    if ok:
        sid = r["id"]
        r2 = api(c, "PATCH", f"/api/scenarios/{sid}", json_data={"nom": "E2E Updated Scenario"})
        test("scenarios", "PATCH /scenarios/:id", is_ok(r2))
        r3 = api(c, "DELETE", f"/api/scenarios/{sid}", expect=[200, 204])
        test("scenarios", "DELETE /scenarios/:id", r3 is None or not (isinstance(r3, dict) and r3.get("_error")))


def test_referentiels(c: httpx.Client):
    """Referentiels — niches, marches."""
    r = api(c, "GET", "/api/niches")
    test("referentiels", "GET /niches (list)", isinstance(r, list))

    r = api(c, "GET", "/api/marches")
    test("referentiels", "GET /marches (list)", isinstance(r, list))


def test_telegram(c: httpx.Client):
    """Telegram — status, groups."""
    r = api(c, "GET", "/api/telegram/status")
    test("telegram", "GET /status", is_ok(r))

    r = api(c, "GET", "/api/telegram/groups")
    test("telegram", "GET /groups (list)", isinstance(r, list) or is_ok(r))


def test_integrations(c: httpx.Client):
    """Integrations — OC/GMS status."""
    r = api(c, "GET", "/api/integrations/oc/status")
    test("integrations", "GET /oc/status", is_ok(r))

    r = api(c, "GET", "/api/integrations/gms/status")
    test("integrations", "GET /gms/status", is_ok(r))


# ── Main ─────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Scale Lab E2E API Tests")
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="API base URL")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Auth token")
    parser.add_argument("--module", default=None, help="Test only one module")
    args = parser.parse_args()

    print(f"\n🔬 Scale Lab E2E API Tests")
    print(f"   Base URL: {args.base_url}")
    print(f"   Token: ***{args.token[-4:]}")
    print(f"   Time: {datetime.now(UTC).isoformat()}")
    print(f"{'─' * 60}\n")

    client = httpx.Client(
        base_url=args.base_url,
        headers={"Authorization": f"Bearer {args.token}"},
        timeout=30,
    )

    modules = {
        "health": test_health,
        "dashboard": test_dashboard,
        "referentiels": test_referentiels,
        "personas": test_personas,
        "comptes": test_comptes,
        "targets": test_targets,
        "presets": test_presets,
        "settings": test_settings,
        "logs": test_logs,
        "proxies": test_proxies,
        "iphones": test_iphones,
        "stats": test_statistiques,
        "veille": test_veille,
        "crm": test_crm,
        "posting": test_posting,
        "liens": test_liens,
        "scenarios": test_scenarios,
        "telegram": test_telegram,
        "integrations": test_integrations,
    }

    if args.module:
        if args.module in modules:
            modules = {args.module: modules[args.module]}
        else:
            print(f"Unknown module: {args.module}")
            print(f"Available: {', '.join(modules.keys())}")
            sys.exit(1)

    for name, fn in modules.items():
        print(f"📦 {name}")
        try:
            fn(client)
        except Exception as e:
            test(name, "EXCEPTION", False, str(e))
        print()

    client.close()

    # Summary
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)

    print(f"{'═' * 60}")
    print(f"  Total: {total}  |  ✅ Passed: {passed}  |  ❌ Failed: {failed}")
    print(f"{'═' * 60}")

    if failed:
        print(f"\n❌ Failed tests:")
        for r in results:
            if not r["passed"]:
                print(f"   • {r['module']} / {r['name']}: {r['detail']}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
