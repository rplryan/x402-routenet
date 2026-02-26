"""
MCP JSON-RPC 2.0 handler for /smithery endpoint.
Implements 3 tools: routenet_route, routenet_simulate, routenet_strategies.
"""
from discovery import discover_services
from router import rank_services, compute_cost, extract_quality, STRATEGIES_DATA
from models import RouteFilter


# Tool schemas
TOOLS = [
    {
        "name": "routenet_route",
        "description": "Route a capability request to the best available x402 service. Returns routing decision, cost breakdown, and quality signals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "capability": {"type": "string", "description": "What you need, e.g. 'web scraping', 'image generation'"},
                "strategy": {"type": "string", "enum": ["best", "cheapest", "fastest", "custom"], "default": "best"},
                "max_price": {"type": "number", "description": "Max service price in USD (optional)"},
                "category": {"type": "string", "description": "Service category filter (optional)"},
                "min_uptime": {"type": "number", "description": "Min uptime % required (optional)"},
            },
            "required": ["capability"],
        },
        "annotations": {"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True, "title": "Route to Best x402 Service"},
    },
    {
        "name": "routenet_simulate",
        "description": "Dry-run routing decision. Preview which x402 service would be selected and why, with top-5 candidates. Free, no execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "capability": {"type": "string", "description": "What you need, e.g. 'web scraping'"},
                "strategy": {"type": "string", "enum": ["best", "cheapest", "fastest", "custom"], "default": "best"},
            },
            "required": ["capability"],
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True, "title": "Simulate Routing Decision"},
    },
    {
        "name": "routenet_strategies",
        "description": "List all routing strategies (best, cheapest, fastest, custom) with scoring formulas and use cases.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False, "title": "List Routing Strategies"},
    },
]


async def handle_mcp_request(body: dict):
    """Handle a single MCP JSON-RPC 2.0 request."""
    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    # ----- Lifecycle -----
    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}, "prompts": {}, "resources": {}},
            "serverInfo": {"name": "x402-routenet", "version": "1.0.0"},
        })

    if method == "notifications/initialized":
        return None  # no response for notifications

    # ----- Tools -----
    if method == "tools/list":
        return ok({"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        return await _call_tool(tool_name, args, ok, err)

    # ----- Prompts -----
    if method == "prompts/list":
        return ok({"prompts": [
            {"name": "route_capability_request", "description": "Guided workflow: describe what you need, RouteNet finds the best x402 service."},
            {"name": "compare_routing_strategies", "description": "Compare best vs cheapest vs fastest strategies for a capability."},
        ]})

    if method == "prompts/get":
        name = params.get("name")
        if name == "route_capability_request":
            return ok({"description": "Route a capability request", "messages": [
                {"role": "user", "content": {"type": "text", "text": "What x402 service do you need? (e.g. 'web scraping', 'LLM inference', 'image generation') Describe it and I'll find the best service."}}
            ]})
        if name == "compare_routing_strategies":
            return ok({"description": "Compare strategies", "messages": [
                {"role": "user", "content": {"type": "text", "text": "What capability do you want to compare strategies for? I'll show you best vs cheapest vs fastest routing decisions."}}
            ]})
        return err(-32602, f"Unknown prompt: {name}")

    # ----- Resources -----
    if method == "resources/list":
        return ok({"resources": [
            {"uri": "routenet://strategies", "name": "Routing Strategies", "description": "All routing strategies with formulas", "mimeType": "application/json"},
            {"uri": "routenet://pricing", "name": "Pricing Model 3", "description": "Fee structure: $0.0002 flat + 0.5% settlement", "mimeType": "application/json"},
        ]})

    if method == "resources/read":
        uri = params.get("uri", "")
        import json
        if uri == "routenet://strategies":
            return ok({"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(STRATEGIES_DATA)}]})
        if uri == "routenet://pricing":
            pricing = {"model": 3, "flat_routing_fee_usd": 0.0002, "settlement_pct": 0.5, "note": "TODO: finalize before v2 launch"}
            return ok({"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(pricing)}]})
        return err(-32602, f"Unknown resource: {uri}")

    return err(-32601, f"Method not found: {method}")


async def _call_tool(name: str, args: dict, ok, err):
    """Execute a tool call."""
    if name == "routenet_route":
        capability = args.get("capability")
        if not capability:
            return err(-32602, "'capability' is required")

        strategy = args.get("strategy", "best")
        filt = None
        if args.get("max_price") or args.get("category") or args.get("min_uptime"):
            filt = RouteFilter(
                max_price=args.get("max_price"),
                category=args.get("category"),
                min_uptime=args.get("min_uptime"),
            )

        services = await discover_services(capability)
        if not services:
            return ok({"content": [{"type": "text", "text": f"No x402 services found for: {capability!r}"}]})

        ranked, reason = rank_services(services, strategy=strategy, filt=filt)
        if not ranked:
            return ok({"content": [{"type": "text", "text": f"No services match the filters. Checked {len(services)} services."}]})

        winner = ranked[0]
        price = float(winner.get("price_usd") or 0.005)
        cost = compute_cost(price)
        quality = extract_quality(winner)

        import json
        result = {
            "routed_to": winner.get("name"),
            "service_url": winner.get("url"),
            "strategy_used": strategy,
            "execution_mode": "simulation",
            "routing_reason": reason,
            "cost_breakdown": {
                "service_price_usd": cost.service_price_usd,
                "routing_fee_usd": cost.routing_fee_usd,
                "settlement_fee_usd": cost.settlement_fee_usd,
                "total_usd": cost.total_usd,
            },
            "quality_signals": {
                "uptime_pct": quality.uptime_pct,
                "avg_latency_ms": quality.avg_latency_ms,
                "trust_score": quality.trust_score,
                "health_status": quality.health_status,
            },
        }
        return ok({"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})

    if name == "routenet_simulate":
        capability = args.get("capability")
        if not capability:
            return err(-32602, "'capability' is required")
        strategy = args.get("strategy", "best")

        services = await discover_services(capability)
        ranked, reason = rank_services(services, strategy=strategy)

        if not ranked:
            return ok({"content": [{"type": "text", "text": f"No x402 services found for: {capability!r}"}]})

        import json
        top5 = []
        for i, svc in enumerate(ranked[:5]):
            top5.append({
                "rank": i + 1,
                "name": svc.get("name"),
                "price_usd": svc.get("price_usd"),
                "uptime_pct": svc.get("uptime_pct"),
                "avg_latency_ms": svc.get("avg_latency_ms"),
                "category": svc.get("category"),
                "health_status": svc.get("health_status") or "unverified",
            })
        result = {
            "capability": capability,
            "strategy": strategy,
            "winner": ranked[0].get("name"),
            "winner_url": ranked[0].get("url"),
            "routing_reason": reason,
            "candidates_evaluated": len(services),
            "top_5": top5,
        }
        return ok({"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})

    if name == "routenet_strategies":
        import json
        result = {
            "strategies": STRATEGIES_DATA,
            "default": "best",
            "pricing_model": {"version": 3, "flat_routing_fee_usd": 0.0002, "settlement_pct": 0.5},
        }
        return ok({"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})

    return err(-32601, f"Unknown tool: {name}")
