# x402 RouteNet

> **The intelligent routing layer for the x402 agent economy.** When 251+ payable services exist, RouteNet decides which one your agent should use — in real time, based on price, latency, uptime, and on-chain trust.

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Network: Base](https://img.shields.io/badge/network-Base-0052FF.svg)](https://base.org)
[![Live on Render](https://img.shields.io/badge/live-render.com-46E3B7.svg)](https://x402-routenet.onrender.com)
[![Discovery API](https://img.shields.io/badge/powered_by-x402_Discovery_API-orange.svg)](https://x402-discovery-api.onrender.com)

**Live API:** https://x402-routenet.onrender.com

---

## The Problem RouteNet Solves

The x402 protocol enables HTTP-native micropayments — but as the ecosystem grows to 251+ live services, agents face a new challenge: **which service do you actually pay?**

Choosing wrong means:
- Paying a service that's offline (wasted transaction)
- Routing to a slow provider when a faster one exists
- Trusting an unverified service with no on-chain reputation
- Hardcoding a single provider and having no fallback when it fails

**RouteNet is the answer.** It sits between your agent and the x402 ecosystem, making real-time routing decisions so your agent doesn't have to.

---

## Architecture: The Complete Agent Payment Stack

```
  ┌─────────────────────────────────────────────────────────┐
  │           Your AI Agent                        │
  └─────────────────────┬───────────────────────────────────┘
                         | "I need web scraping"
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │          x402 Discovery API              │  ← FIND
  │  x402-discovery-api.onrender.com         │
  │  251+ indexed services with trust scores │
  └─────────────────────┬───────────────────────────────────┘
                         | "Here are 12 web scraping services"
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │          x402 RouteNet                    │  ← ROUTE
  │  x402-routenet.onrender.com              │
  │  health + latency + ERC-8004 trust score │
  └──────────┬──────────────┬──────────────────────────────┘
           |              |
           ▼              ▼
  ┌─────────────┐  ┌────────────────────────────┐
  │ Provider A  │  │ Provider B (degraded → skip)│
  │ (healthy ✓) │  │               ✗              │
  └──────┬──────┘  └────────────────────────────┘
         |
         ▼
  ┌─────────────────────────────────────────────────────────┐
  │          x402 Payment Harness              │  ← PAY
  │  pip install x402-payment-harness          │
  │  EIP-712 sign → X-PAYMENT header → HTTP 200 │
  └─────────────────────────────────────────────────────────┘
```

**Discover → Route → Pay.** The complete agent-native payment stack for x402, built on Base.

---

## Routing Strategies

Four production-grade strategies, each tuned for a different agent workload:

| Strategy | Algorithm | Best For |
|---|---|---|
| `best` | Composite: uptime (40%) + speed (30%) + ERC-8004 trust (30%) | **Recommended default** — balances reliability, performance, trust |
| `cheapest` | Lowest price among services with >80% uptime | High-volume agents, cost-sensitive workloads |
| `fastest` | Lowest average latency among healthy services | Real-time applications, user-facing agents |
| `custom` | Filter by `max_price`, `min_uptime`, `category`, `min_trust_score`, then `best` composite | Fine-grained agent-defined constraints |

### ERC-8004 Trust Integration

The `best` strategy (and `custom`) factor in on-chain identity via ERC-8004:

```
score = (uptime_pct / 100) × 0.4
      + (1 - min(latency_ms / 1000, 1)) × 0.3
      + (trust_score / 100) × 0.3   ← ERC-8004 verified identity
```

Services with ERC-8004 registration are scored on verified on-chain identity — not self-reported metadata. **Bad actors cannot game routing** by submitting inflated claims to the registry.

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/route` | POST | Route a capability request to the optimal x402 service |
| `/simulate` | GET | Dry-run routing decision (no live request) |
| `/strategies` | GET | All strategies with formulas and use cases |
| `/routes/recent` | GET | Last 100 routing decisions with timestamps and costs |
| `/health` | GET | Service health, version, routes processed |

### `POST /route`

```bash
curl -X POST https://x402-routenet.onrender.com/route \
  -H "Content-Type: application/json" \
  -d '{"capability": "web scraping", "strategy": "best"}'
```

```json
{
  "routed_to": "Firecrawl",
  "url": "https://api.firecrawl.dev/x402",
  "strategy_used": "best",
  "total_usd": 0.001205,
  "fallback_available": true,
  "trust_score": 85,
  "avg_latency_ms": 142
}
```

### `GET /simulate`

```bash
curl "https://x402-routenet.onrender.com/simulate?capability=token+prices&strategy=cheapest"
# Dry-run: shows which provider would be selected without executing
```

### `GET /health`

```bash
curl https://x402-routenet.onrender.com/health
# {"status": "healthy", "version": "1.0.0", "routes_processed": 5}
```

---

## Quick Start

```python
import requests

# Route to the optimal x402 service for any capability
route = requests.post(
    "https://x402-routenet.onrender.com/route",
    json={"capability": "web scraping", "strategy": "best"}
).json()

print(f"Route to: {route['routed_to']} at ${route['total_usd']}/call")
# Route to: Firecrawl at $0.001205/call
```

No API key. No configuration. Zero setup for agents.

---

## Full Stack Integration

```python
import requests
from x402_harness import X402Client  # pip install x402-payment-harness

# 1. Discover available services
discovery = requests.get(
    "https://x402-discovery-api.onrender.com/discover",
    params={"query": "token price data", "max_price_usd": "0.01"}
).json()
print(f"Found {len(discovery['services'])} services")

# 2. Route to the optimal provider
route = requests.post(
    "https://x402-routenet.onrender.com/route",
    json={"capability": "token price data", "strategy": "best"}
).json()
print(f"Routing to: {route['routed_to']} (trust score: {route.get('trust_score', 'N/A')}%)")

# 3. Pay and consume
client = X402Client(private_key="0xYOUR_PRIVATE_KEY")
result = client.get(route["url"])
print(f"Result: {result}")
```

This implements the ["Dynamic Endpoint Shopper"](https://github.com/coinbase/x402/blob/main/PROJECT-IDEAS.md) pattern from the coinbase/x402 project ideas — an agent that discovers a service registry, selects the best provider based on real-time signals, and pays — all in three API calls.

---

## Use Cases

**AI Agent Orchestration** — An agent chooses between 12 web scraping services. RouteNet picks the best uptime/latency/trust composite — without the agent implementing health checking logic.

**Cost-Optimized Data Pipelines** — 10,000 token price queries/day with `strategy: cheapest` automatically routes to the lowest-price service meeting the uptime threshold.

**Mission-Critical Flows** — Time-sensitive DeFi agents use `strategy: fastest` with automatic fallback if the primary provider degrades.

**Trust-Gated Networks** — Require ERC-8004 registration before a provider can receive traffic via `custom` strategy with `min_trust_score: 50`.

---

## Self-Hosting

```bash
git clone https://github.com/rplryan/x402-routenet
cd x402-routenet
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Or use the hosted instance at https://x402-routenet.onrender.com — no setup required.

**Environment variables:**

| Variable | Description | Default |
|---|---|---|
| `PORT` | Port to listen on | `8000` |
| `HEALTH_CHECK_INTERVAL` | Seconds between provider health polls | `30` |
| `LATENCY_WINDOW` | Rolling window size for latency averaging | `10` |
| `DISCOVERY_API_URL` | Discovery API endpoint | `https://x402-discovery-api.onrender.com` |

---

## The x402 Infrastructure Suite

| Tool | Role | Status |
|---|---|---|
| [x402 Discovery API](https://github.com/rplryan/x402-discovery-api) | **Find** — 251+ x402 services indexed, quality signals, ERC-8004 trust scores, auto-scanner | ✅ Live |
| [x402 RouteNet](https://github.com/rplryan/x402-routenet) | **Route** — Intelligent routing: health + latency + trust → optimal provider | ✅ Live |
| [x402 Payment Harness](https://github.com/rplryan/x402-payment-harness) | **Pay** — EOA-based EIP-712 signing, proven on Base mainnet | ✅ PyPI |
| [x402 Discovery MCP](https://github.com/rplryan/x402-discovery-mcp) | **Agent tools** — 5 MCP tools for Claude/Cursor/Windsurf, Smithery 100/100 | ✅ Live |

Together: the complete open-source infrastructure for x402 service discovery and payment on Base.

---

## Version History

| Version | Changes |
|---|---|
| 1.0.0 | Initial release: 4 routing strategies with ERC-8004 trust integration, composite scoring formula, background health monitoring, dry-run simulate endpoint, routes/recent audit log |

---

## License

MIT © 2024 rplryan
