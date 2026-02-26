"""
x402 RouteNet — Smart routing infrastructure for the x402 ecosystem.

Routes AI agent capability requests to the best available x402 service
based on price, speed, or composite quality scoring (with ERC-8004 trust).

Pricing Model 3 (transparent, not yet collected):
  - $0.0002 flat routing fee per decision
  - 0.5% settlement fee on service price
  TODO: set ROUTENET_WALLET env var when ready to collect fees
"""
import os
from datetime import datetime, timezone
from collections import deque
from typing import Optional, Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from discovery import discover_services, DISCOVERY_API_URL
from router import rank_services, compute_cost, extract_quality, STRATEGIES_DATA
from models import RouteRequest, RouteFilter
from mcp_server import handle_mcp_request


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="x402 RouteNet",
    description="Smart routing infrastructure for the x402 ecosystem",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory recent routes (resets on restart)
_recent_routes: deque = deque(maxlen=100)

ROUTENET_WALLET = os.getenv("ROUTENET_WALLET", "")  # TODO: set when Pricing Model 3 is finalized


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "discovery_api": DISCOVERY_API_URL,
        "pricing_model": {
            "version": 3,
            "flat_routing_fee_usd": 0.0002,
            "settlement_pct": 0.5,
            "collection_enabled": bool(ROUTENET_WALLET),
            "wallet": ROUTENET_WALLET or None,
        },
        "routes_processed": len(_recent_routes),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/route")
async def route_request(req: RouteRequest):
    """
    Route a capability request to the best available x402 service.
    
    MVP: Returns routing DECISION (which service, why, cost breakdown).
    Execution mode is 'simulation' — actual x402 payment calls come in v2.
    """
    services = await discover_services(req.capability)
    if not services:
        return JSONResponse(
            status_code=404,
            content={"error": f"No x402 services found for: {req.capability!r}", "capability": req.capability},
        )

    ranked, reason = rank_services(services, strategy=req.strategy, filt=req.filter)
    if not ranked:
        return JSONResponse(
            status_code=404,
            content={
                "error": "No services match the given filters",
                "candidates_checked": len(services),
                "strategy": req.strategy,
                "filter": req.filter.model_dump() if req.filter else None,
            },
        )

    winner = ranked[0]
    price = float(winner.get("price_usd") or 0.005)
    cost = compute_cost(price)
    quality = extract_quality(winner)

    # Record in recent routes
    route_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "capability": req.capability,
        "strategy": req.strategy,
        "routed_to": winner.get("name"),
        "total_usd": cost.total_usd,
    }
    _recent_routes.appendleft(route_record)

    return {
        "execution_mode": "simulation",  # v2 will execute actual x402 payments
        "capability": req.capability,
        "routed_to": winner.get("name"),
        "service_url": winner.get("url"),
        "service_category": winner.get("category"),
        "strategy_used": req.strategy,
        "candidates_evaluated": len(services),
        "routing_reason": reason,
        "cost_breakdown": {
            "service_price_usd": cost.service_price_usd,
            "routing_fee_usd": cost.routing_fee_usd,
            "settlement_fee_usd": cost.settlement_fee_usd,
            "total_usd": cost.total_usd,
            # TODO: Pricing Model 3 — collect fees when ROUTENET_WALLET configured
        },
        "quality_signals": {
            "uptime_pct": quality.uptime_pct,
            "avg_latency_ms": quality.avg_latency_ms,
            "trust_score": quality.trust_score,
            "health_status": quality.health_status,
            "erc8004_verified": quality.erc8004_verified,
        },
        "input_forwarded": req.input,  # v2: will be POSTed to service_url
    }


@app.get("/simulate")
async def simulate(capability: str, strategy: str = "best"):
    """
    Dry-run routing decision. Returns which service would be selected
    and why, without executing anything.
    """
    services = await discover_services(capability)
    ranked, reason = rank_services(services, strategy=strategy)

    if not ranked:
        return JSONResponse(
            status_code=404,
            content={"error": f"No services found for: {capability!r}"},
        )

    # Top 5 candidates with scores
    top5 = []
    for i, svc in enumerate(ranked[:5]):
        cost = compute_cost(float(svc.get("price_usd") or 0.005))
        top5.append({
            "rank": i + 1,
            "name": svc.get("name"),
            "url": svc.get("url"),
            "price_usd": svc.get("price_usd"),
            "uptime_pct": svc.get("uptime_pct"),
            "avg_latency_ms": svc.get("avg_latency_ms"),
            "category": svc.get("category"),
            "health_status": svc.get("health_status") or "unverified",
            "trust_score": svc.get("erc8004_reputation_score") or svc.get("trust_score"),
            "total_cost_usd": cost.total_usd,
        })

    return {
        "capability": capability,
        "strategy": strategy,
        "winner": ranked[0].get("name"),
        "winner_url": ranked[0].get("url"),
        "routing_reason": reason,
        "candidates_evaluated": len(services),
        "top_5": top5,
    }


@app.get("/strategies")
async def strategies():
    """List all routing strategies with descriptions and scoring formulas."""
    return {
        "strategies": STRATEGIES_DATA,
        "default": "best",
        "pricing_model": {
            "version": 3,
            "description": "Flat routing fee + settlement percentage",
            "flat_routing_fee_usd": 0.0002,
            "settlement_pct": 0.5,
            "note": "TODO: finalize exact values before v2 launch",
        },
    }


@app.get("/routes/recent")
async def recent_routes(limit: int = 10):
    """Return the last N routing decisions (in-memory, resets on restart)."""
    routes = list(_recent_routes)[:min(limit, 100)]
    return {
        "count": len(routes),
        "routes": routes,
    }


# ---------------------------------------------------------------------------
# MCP endpoint (Smithery-compatible)
# ---------------------------------------------------------------------------

@app.post("/smithery")
async def mcp_endpoint(request: Request):
    """MCP JSON-RPC 2.0 endpoint — implements 3 tools for agent frameworks."""
    body = await request.json()
    result = await handle_mcp_request(body)
    if result is None:
        return Response(status_code=204)
    return JSONResponse(result)


@app.get("/smithery")
async def mcp_info():
    """Return MCP server info for GET requests."""
    return {
        "name": "x402-routenet",
        "version": "1.0.0",
        "description": "Smart routing infrastructure for x402 services",
        "tools": ["routenet_route", "routenet_simulate", "routenet_strategies"],
        "mcp_url": "/smithery",
    }


# ---------------------------------------------------------------------------
# Well-known server card
# ---------------------------------------------------------------------------

@app.get("/.well-known/mcp/server-card.json")
async def server_card():
    """Serve the MCP server card for Smithery discovery."""
    import json
    try:
        with open(".well-known/mcp/server-card.json") as f:
            return JSONResponse(json.load(f))
    except FileNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"error": "server-card.json not found"},
        )


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "service": "x402 RouteNet",
        "version": "1.0.0",
        "description": "Smart routing infrastructure for the x402 ecosystem",
        "endpoints": {
            "POST /route": "Route a capability request to the best x402 service",
            "GET /simulate": "Dry-run routing decision",
            "GET /strategies": "List available routing strategies",
            "GET /routes/recent": "Recent routing decisions",
            "GET /health": "Service health",
            "POST /smithery": "MCP JSON-RPC 2.0 endpoint",
        },
        "docs": "/docs",
        "discovery_api": DISCOVERY_API_URL,
        "github": "https://github.com/rplryan/x402-routenet",
    }
