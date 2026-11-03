"""Real proxy tester — connects through the proxy, measures latency,
retrieves exit IP/country, checks blacklists."""

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger("proxy_tester")

# Blacklist DNS zones (DNSBL) — IP is reversed and prepended
DNSBL_ZONES = [
    ("zen.spamhaus.org", "Spamhaus"),
    ("bl.spamcop.net", "SpamCop"),
    ("b.barracudacentral.org", "Barracuda"),
    ("dnsbl.sorbs.net", "SORBS"),
]

IP_CHECK_URL = "https://ipinfo.io/json"
IP_CHECK_TIMEOUT = 15.0


@dataclass
class ProxyTestResult:
    success: bool
    exit_ip: str | None = None
    exit_country: str | None = None
    exit_org: str | None = None
    latency_ms: int | None = None
    blacklists: list[str] | None = None
    error: str | None = None
    is_datacenter: bool = False


async def _check_dnsbl(ip: str) -> list[str]:
    """Check an IP against DNS blacklists."""
    parts = ip.split(".")
    if len(parts) != 4:
        return []
    reversed_ip = ".".join(reversed(parts))
    hits = []

    async def check_one(zone: str, label: str):
        query = f"{reversed_ip}.{zone}"
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.getaddrinfo(query, None), timeout=5.0
            )
            hits.append(label)
        except (OSError, asyncio.TimeoutError):
            pass  # Not listed or timeout = not blacklisted

    tasks = [check_one(zone, label) for zone, label in DNSBL_ZONES]
    await asyncio.gather(*tasks)
    return hits


def _detect_datacenter(org: str | None, hosting: bool | None) -> bool:
    """Heuristic to detect datacenter/VPN IPs."""
    if hosting:
        return True
    if not org:
        return False
    dc_keywords = [
        "hosting", "cloud", "server", "datacenter", "data center",
        "ovh", "hetzner", "digitalocean", "amazon", "aws", "google",
        "microsoft", "azure", "linode", "vultr", "contabo", "scaleway",
        "oracle", "ibm", "rackspace", "godaddy", "cloudflare",
    ]
    org_lower = org.lower()
    return any(kw in org_lower for kw in dc_keywords)


async def test_proxy(
    ip: str,
    proxy_type: str = "socks5",
) -> ProxyTestResult:
    """Test a proxy by connecting through it and measuring latency, exit IP, blacklists.

    Args:
        ip: Proxy address in format host:port or host:port:user:pass
        proxy_type: Protocol — socks5, http, https
    """
    parts = ip.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        proxy_url = f"{proxy_type}://{user}:{password}@{host}:{port}"
    elif len(parts) == 2:
        host, port = parts
        proxy_url = f"{proxy_type}://{host}:{port}"
    else:
        return ProxyTestResult(success=False, error=f"Format IP invalide: {ip}")

    try:
        t0 = time.monotonic()

        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=httpx.Timeout(IP_CHECK_TIMEOUT),
            verify=False,
        ) as client:
            resp = await client.get(IP_CHECK_URL)
            latency_ms = int((time.monotonic() - t0) * 1000)

            if resp.status_code != 200:
                return ProxyTestResult(
                    success=False,
                    latency_ms=latency_ms,
                    error=f"ipinfo returned {resp.status_code}",
                )

            data = resp.json()
            exit_ip = data.get("ip", "")
            exit_country = data.get("country", "")
            exit_org = data.get("org", "")
            is_hosting = data.get("privacy", {}).get("hosting", False) if "privacy" in data else None

        # Check blacklists in parallel
        blacklists = await _check_dnsbl(exit_ip) if exit_ip else []

        is_dc = _detect_datacenter(exit_org, is_hosting)

        return ProxyTestResult(
            success=True,
            exit_ip=exit_ip,
            exit_country=exit_country,
            exit_org=exit_org,
            latency_ms=latency_ms,
            blacklists=blacklists,
            is_datacenter=is_dc,
        )

    except httpx.ProxyError as e:
        return ProxyTestResult(success=False, error=f"Connexion proxy impossible: {e}")
    except httpx.ConnectTimeout:
        return ProxyTestResult(success=False, error="Timeout connexion au proxy")
    except httpx.ReadTimeout:
        return ProxyTestResult(success=False, error="Timeout lecture via proxy")
    except Exception as e:
        logger.exception("proxy test failed")
        return ProxyTestResult(success=False, error=str(e))
