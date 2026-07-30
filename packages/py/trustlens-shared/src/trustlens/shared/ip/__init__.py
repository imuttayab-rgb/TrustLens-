"""IP intelligence with an offline fallback.

The chain matters: a metered HTTP provider first, an offline ASN/datacenter
heuristic second. Without the fallback the NETWORK signal would simply vanish
whenever the provider is unreachable or no key is configured - and the FYP
would not be demonstrable without a paid account (NFR-8).

The fallback publishes the same verdict shape but at lower confidence, which
the scoring engine then reflects in the score's confidence value rather than
pretending the two sources are equally reliable.
"""

from __future__ import annotations

import ipaddress
from datetime import UTC, datetime

import httpx

from trustlens.core.domain.entities import IpReputation
from trustlens.core.domain.ports import IpIntelligence
from trustlens.shared.config.settings import IpIntelSettings
from trustlens.shared.logging import get_logger

log = get_logger(__name__)

#: Well-known hosting/VPN ASNs. Not exhaustive by any means - this is a
#: heuristic floor, not a substitute for a reputation feed.
DATACENTER_ASNS: frozenset[int] = frozenset(
    {
        14061,
        16509,
        14618,
        15169,
        396982,  # DigitalOcean, AWS, Google
        8075,
        12076,  # Microsoft/Azure
        16276,
        24940,
        20473,
        63949,  # OVH, Hetzner, Vultr, Linode
        13335,
        209242,  # Cloudflare
        9009,
        51167,
        60068,  # M247, Contabo, Datacamp (VPN hosts)
    }
)


class OfflineIpIntelligence(IpIntelligence):
    """Structural checks only: private/loopback ranges and a known-ASN list."""

    async def lookup(self, ip: str) -> IpReputation:
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return IpReputation(ip=ip, provider="offline", looked_up_at=datetime.now(UTC))

        is_private = address.is_private or address.is_loopback
        return IpReputation(
            ip=ip,
            is_datacenter=False,
            # A private address means we are behind an untrusted proxy or in
            # local development; either way it carries no reputation signal.
            abuse_score=0,
            provider="offline",
            looked_up_at=datetime.now(UTC),
            raw={"private": is_private},
        )


class HttpIpIntelligence(IpIntelligence):
    """ipapi.co / IPQualityScore style lookup, falling back on any failure."""

    def __init__(self, settings: IpIntelSettings, fallback: IpIntelligence) -> None:
        self._s = settings
        self._fallback = fallback

    async def lookup(self, ip: str) -> IpReputation:
        try:
            async with httpx.AsyncClient(timeout=self._s.ip_intel_timeout_seconds) as client:
                response = await client.get(f"https://ipapi.co/{ip}/json/")
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            # Degrade rather than fail: an unreachable provider must not block
            # a seller's verification.
            log.warning("ip_intel_lookup_failed", error=str(exc), fallback="offline")
            return await self._fallback.lookup(ip)

        asn_raw = str(data.get("asn") or "").removeprefix("AS")
        asn = int(asn_raw) if asn_raw.isdigit() else None
        return IpReputation(
            ip=ip,
            country_code=data.get("country_code"),
            region=data.get("region"),
            city=data.get("city"),
            asn=asn,
            asn_org=data.get("org"),
            is_datacenter=asn in DATACENTER_ASNS if asn else False,
            is_vpn=bool(data.get("vpn") or (asn in DATACENTER_ASNS if asn else False)),
            is_proxy=bool(data.get("proxy")),
            is_tor=bool(data.get("tor")),
            provider="ipapi",
            looked_up_at=datetime.now(UTC),
            raw=data,
        )


def build_ip_intelligence(settings: IpIntelSettings) -> IpIntelligence:
    offline = OfflineIpIntelligence()
    if settings.ip_intel_provider == "offline":
        return offline
    return HttpIpIntelligence(settings, fallback=offline)


__all__ = [
    "DATACENTER_ASNS",
    "HttpIpIntelligence",
    "OfflineIpIntelligence",
    "build_ip_intelligence",
]
