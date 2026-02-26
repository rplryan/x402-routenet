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
    """
    cache_key = f"{capability.lower().strip()}:{limit}"
    now = time.time()

    # Return cached result if fresh
    if cache_key in _cache:
        cached_at, cached_results = _cache[cache_key]
        if now - cached_at < CACHE_TTL_SECONDS:
            return cached_results

    try:
        url = f"{DISCOVERY_API_URL}/discover"
        params = {"q": capability, "limit": limit}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        # Discovery API returns: { "services": [...], "count": N, ... }
        if isinstance(data, dict):
            services = data.get("services") or data.get("results") or []
        elif isinstance(data, list):
            services = data
        else:
            services = []

        # Also try /catalog as fallback if discover returns empty
        if not services:
            services = await _fetch_catalog_fallback(capability)

        _cache[cache_key] = (now, services)
        return services

    except Exception as e:
        # On error, return cached (stale) data if available, otherwise empty
        if cache_key in _cache:
            _, stale = _cache[cache_key]
            return stale
        return []


async def _fetch_catalog_fallback(capability: str) -> list[dict]:
    """Fallback: get full catalog and filter by keyword."""
    try:
        url = f"{DISCOVERY_API_URL}/catalog"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        if isinstance(data, dict):
            all_services = data.get("services") or data.get("catalog") or []
        elif isinstance(data, list):
            all_services = data
        else:
            return []

        # Simple keyword match on name, description, capability_tags, tags
        kw = capability.lower()
        matched = []
        for svc in all_services:
            text = " ".join([
                str(svc.get("name") or ""),
                str(svc.get("description") or ""),
                " ".join(svc.get("capability_tags") or []),
                " ".join(svc.get("tags") or []),
                str(svc.get("category") or ""),
            ]).lower()
            if kw in text:
                matched.append(svc)

        return matched

    except Exception:
        return []
