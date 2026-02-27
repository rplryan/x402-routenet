# x402 RouteNet

> **The intelligent execution layer for x402** — when you've discovered a service and verified its trust, RouteNet picks the optimal path to pay and execute.

[![Live API](https://img.shields.io/badge/API-Live%20v1.0.0-brightgreen)](https://x402-routenet.onrender.com)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![x402](https://img.shields.io/badge/protocol-x402-orange)](https://x402.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Live:** https://x402-routenet.onrender.com · **4 routing strategies** · **Smart fallback** · **Partner of x402 Discovery**

---

## What RouteNet Solves

When multiple x402 services offer the same capability (e.g., three different AI search APIs, all accepting x402 payments), an agent needs to decide:

- Which one is cheapest right now?
- Which one has the best recent uptime?
- Which one has the highest trust score?
- If my preferred one is down, what's the fallback?

Without routing intelligence, agents either hardcode a single endpoint (brittle) or make expensive multi-step decisions at inference time (slow, unpredictable).

**RouteNet is a dedicated routing layer** that answers these questions once, cheaply, so agents can execute with confidence.

---

## Architecture

```
          AI Agent
              │
    ┌─────────┴─────────┐
    │   x402 RouteNet      │
    │  (routing engine)    │
    └─────────┬─────────┘
                 │
    ┌─────────┴─────────┐
    │   x402 Discovery     │
    │   (service catalog)  │
    └───┬────┬────┬───┘
         │       │      │
     Service  Service  Service
       A        B        C
     (x402)  (x402)   (x402)
```

RouteNet sits between the agent and the service catalog. It queries Discovery, applies routing strategy, and returns a single recommended endpoint — with fallbacks.

---

## Routing Strategies

| Strategy | What It Optimizes | Best For |
|---|---|---|
| `cost` | Lowest price per call | High-volume, cost-sensitive agents |
| `performance` | Best historical latency + uptime | Time-sensitive, production agents |
| `reliability` | Highest uptime over 30 days | Mission-critical workflows |
| `composite` | Weighted score: 40% cost, 30% performance, 30% reliability | General-purpose, default |

---

## API Endpoints

### `POST /route`

Get the optimal service for a capability:

```bash
curl -X POST https://x402-routenet.onrender.com/route \
  -H "Content-Type: application/json" \
  -d '{"capability": "research", "strategy": "composite", "max_price_usd": 0.05}'   
```

Response:
```json
{
  "recommended": {
    "name": "Tavily AI Search",
    "endpoint": "https://api.tavily.com/x402/search",
    "price_usd": 0.002,
    "uptime_30d": 99.7,
    "composite_score": 94.2,
    "facilitator_compatible": true,
    "erc8004_verified": true
  },
  "fallbacks": [
    {"name": "Exa AI Search", "endpoint": "...", "price_usd": 0.003}
  ],
  "strategy_used": "composite",
  "routing_time_ms": 12
}
```

### `GET /strategies`

List available routing strategies and their parameters.

### `GET /health`

RouteNet health check + upstream Discovery API status.

### `GET /metrics`

Current routing table: all services with scores across all strategies.

### `GET /docs`

Interactive API documentation (Swagger UI).

---

## Integration with x402 Discovery

RouteNet is designed as a companion to the [x402 Service Discovery MCP](https://github.com/rplryan/x402-discovery-mcp):

- **Discovery** finds and catalogs services, provides trust signals
- **RouteNet** optimizes which service to use given current conditions
- **Result**: agents don't just discover services — they execute optimally

A complete agentic commerce workflow:
```
1. x402_discover("research")        # Discovery: what services exist?
2. x402_trust(wallet)               # Trust: which are legitimate?
3. x402_facilitator_check(network)  # Compatibility: can I pay?
4. POST /route (strategy=composite) # RouteNet: which one right now?
5. Execute x402 payment             # Pay and receive service
```

---

## Proven: End-to-End Payment Stack

RouteNet is part of a complete x402 stack with a **confirmed on-chain payment**:

| Field | Value |
|---|---|
| **Transaction** | [`0xb0ef774...`](https://basescan.org/tx/0xb0ef774a7a26cdb370c305a625b2cf1bd6d7bb98f2ca16119d953bdcebc7e860) |
| **Network** | Base mainnet |
| **Amount** | 0.005 USDC |
| **Block** | 42707833 — confirmed |

---

## Quickstart

```bash
git clone https://github.com/rplryan/x402-routenet
cd x402-routenet
pip install -r requirements.txt
python app.py
```

Or use the live API directly: `https://x402-routenet.onrender.com`

---

## Related Projects

- **[x402 Discovery MCP](https://github.com/rplryan/x402-discovery-mcp)** — Service catalog, trust layer, MCP tools for Claude/Cursor/Windsurf
- **[x402 Payment Harness](https://github.com/rplryan/x402-payment-harness)** — EOA-based payment testing without CDP dependencies

---

## License

MIT
