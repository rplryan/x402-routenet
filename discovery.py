"""
Discovery API client with 30-second TTL cache.
Fetches x402 services from the x402 Service Discovery API.
"""
import time
import os
import httpx
from typing import Optional

DISCOVERY_API_URL = os.getenv("DISCOVERY_API_URL", "https://x402-discovery-api.onrender.com")
CACHE_TTL_SECONDS = 30

# Simple in-memory cache: { query_key: (timestamp, results) }
_cache: dict[str, tuple[float, list]] = {}


async def discover_services(capability: str, limit: int = 10) -> list[dict]:
    """
    Fetch x402 services matching the capability from the Discovery API.
    Results cached for 30 seconds to reduce API calls during rapid routing.
    Falls back to /catalog keyword filtering if /discover is unavailable.
    """
    cache_key = f"{capability.lower().strip()}:{limit}"
    now = time.time()

    # Return cached result if fresh
    if cache_key in _cache:
        cached_at, cached_results = _cache[cache_key]
        if now - cached_at < CACHE_TTL_SECONDS:
            return cached_results

    # Try /discover endpoint first
    try:
        url = f"{DISCOVERY_API_URL}/discover"
        params = {"q": capability, "limit": limit}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)

        # /discover requires x402 payment — fall back to catalog
        if response.status_code in (402, 402):
            services = await _fetch_catalog_fallback(capability)
        elif response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                services = (data.get("services")
                            or data.get("results")
                            or data.get("endpoints")
                            or [])
            elif isinstance(data, list):
                services = data
            else:
                services = []
            # Still fall back if empty
            if not services:
                services = await _fetch_catalog_fallback(capability)
        else:
            services = await _fetch_catalog_fallback(capability)

    except Exception:
        services = await _fetch_catalog_fallback(capability)
        if not services and cache_key in _cache:
            _, stale = _cache[cache_key]
            return stale

    _cache[cache_key] = (now, services)
    return services


async def _fetch_catalog_fallback(capability: str) -> list[dict]:
    """Fallback: get full catalog and filter by keyword matching."""
    try:
        url = f"{DISCOVERY_API_URL}/catalog"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        # Discovery API /catalog returns {"endpoints": [...]}
        if isinstance(data, dict):
            all_services = (data.get("endpoints")
                            or data.get("services")
                            or data.get("catalog")
                            or data.get("results")
                            or [])
        elif isinstance(data, list):
            all_services = data
        else:
            return []

        # Multi-word keyword matching: split into words, match any
        words = [w for w in capability.lower().split() if len(w) > 2]
        if not words:
            words = [capability.lower()]

        matched = []
        for svc in all_services:
            text = " ".join([
                str(svc.get("name") or ""),
                str(svc.get("description") or ""),
                " ".join(svc.get("capability_tags") or []),
                " ".join(svc.get("tags") or []),
                str(svc.get("category") or ""),
            ]).lower()
            # Match if ANY of the capability words appear in the service text
            if any(w in text for w in words):
                matched.append(svc)

        return matched

    except Exception:
        return []
