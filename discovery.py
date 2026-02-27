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

# Synonym / category expansion: map user terms → catalog terms
CAPABILITY_SYNONYMS: dict[str, list[str]] = {
    # AI & ML
    "ai inference": ["compute", "ai", "generation", "language model", "llm"],
    "inference": ["compute", "ai", "generation"],
    "llm": ["compute", "ai", "generation", "language"],
    "language model": ["compute", "ai", "generation"],
    "image generation": ["image", "generation", "art", "visual"],
    "image": ["image", "art", "visual", "photo"],
    # Data
    "web scraping": ["scraping", "extraction", "crawl", "data"],
    "scraping": ["extraction", "crawl", "data"],
    "data extraction": ["extraction", "data", "scraping"],
    "search": ["search", "research", "data"],
    "price": ["price", "financial", "crypto", "market"],
    "crypto price": ["price", "financial", "crypto", "blockchain"],
    "stock": ["financial", "market", "price", "trading"],
    # Communication
    "email": ["email", "communication", "notification"],
    "sms": ["sms", "communication", "notification"],
    "notification": ["notification", "communication", "messaging"],
    # Storage
    "storage": ["storage", "database", "file"],
    "database": ["storage", "database"],
    "file storage": ["storage", "file"],
    # Summarization
    "summarize": ["summarization", "summary", "nlp"],
    "summarization": ["summarization", "summary", "nlp", "text"],
    "text processing": ["summarization", "nlp", "text", "extraction"],
    # Other
    "translation": ["translation", "language", "nlp"],
    "monitoring": ["monitoring", "analytics", "uptime"],
    "routing": ["routing", "infrastructure", "network"],
}


def expand_capability(capability: str) -> list[str]:
    """Expand a capability string to a list of search terms using synonyms."""
    lower = capability.lower().strip()
    # Direct match
    if lower in CAPABILITY_SYNONYMS:
        return CAPABILITY_SYNONYMS[lower]
    # Partial match — check if any synonym key is a substring
    expanded = []
    for key, synonyms in CAPABILITY_SYNONYMS.items():
        if key in lower or lower in key:
            expanded.extend(synonyms)
    if expanded:
        return list(set(expanded))
    # Fallback: original words (filter short ones)
    words = [w for w in lower.split() if len(w) > 2]
    return words if words else [lower]


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
    """Fallback: get full catalog and filter by keyword matching with synonym expansion."""
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

        # Expand capability to search terms using synonym map
        search_terms = expand_capability(capability)

        matched = []
        for svc in all_services:
            text = " ".join([
                str(svc.get("name") or ""),
                str(svc.get("description") or ""),
                " ".join(svc.get("capability_tags") or []),
                " ".join(svc.get("tags") or []),
                str(svc.get("category") or ""),
            ]).lower()
            # Match if ANY search term appears in the service text
            if any(term in text for term in search_terms):
                matched.append(svc)

        return matched

    except Exception:
        return []
