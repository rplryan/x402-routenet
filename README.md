# x402 RouteNet

Smart routing infrastructure for the x402 ecosystem. The **execution layer** complementary to [x402 Service Discovery](https://github.com/rplryan/x402-discovery-mcp).

[![Live API](https://img.shields.io/badge/API-Live-brightgreen)](https://x402-routenet.onrender.com)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![x402](https://img.shields.io/badge/protocol-x402-orange)](https://x402.org)

## Architecture

```
          AI Agent
             │
             ▼
    ┌─────────────────┐
    │  POST /route    │  ← "I need web scraping capability"
    │  x402 RouteNet  │
    └────────┬────────┘
             │ queries
             ▼
    ┌─────────────────┐
    │  Discovery API  │  ← quality signals, ERC-8004 trust
    │  (catalog layer)│
    └────────┬────────┘
             │ ranks by strategy
             ▼
    ┌─────────────────┐
    │ Best x402 Svc   │  ← cheapest | fastest | best | custom
    └─────────────────┘
```

**Discovery** = what services exist, quality signals, trust scores  
**RouteNet** = given a request, route to the best option, return cost breakdown

## Quick Start

```bash
curl -X POST https://x402-routenet.onrender.com/route \\
  -H "Content-Type: application/json" \\
  -d \'{"capability": "web scraping", "strategy": "best"}\'
```

Response:
```json
{
  "execution_mode": "simulation",
  "capability": "web scraping",
  "routed_to": "Firecrawl — Web Scraping & Extraction API",
  "service_url": "https://api.firecrawl.dev",
  "strategy_used": "best",
  "cost_breakdown": {
    "service_price_usd": 0.002,
    "routing_fee_usd": 0.0002,
    "settlement_fee_usd": 0.00001,
    "total_usd": 0.00221
  },
  "quality_signals": {
    "uptime_pct": 99.2,
    "avg_latency_ms": 412,
    "trust_score": 0,
    "health_status": "healthy",
    "erc8004_verified": false
  }
}
```

## Routing Strategies

| Strategy | Formula | Use Case |
|---|---|---|
| `best` (default) | 40% quality + 30% price + 30% uptime | Balanced |
| `cheapest` | lowest `price_usd` | Cost-sensitive agents |
| `fastest` | lowest `avg_latency_ms` | Latency-sensitive |
| `custom` | user-defined weights | Specialized agents |

## API Endpoints

| Endpoint | Description |
|---|---|
| `POST /route` | Route a capability request |
| `GET /simulate?capability=X` | Dry-run, see top 5 candidates |
| `GET /strategies` | List strategies + pricing model |
| `GET /routes/recent` | Last 100 routing decisions |
| `GET /health` | Service health |
| `POST /smithery` | MCP JSON-RPC endpoint |

## Pricing Model 3

Transparent, predictable fees:
- **$0.0002 flat routing fee** per decision (regardless of service price)
- **0.5% settlement fee** on the service\'s transaction value

Flat fee avoids percentage-bypass at higher price points. Agents know exactly what routing costs regardless of the underlying service price.

*Note: Fee collection is not yet enabled in MVP. The cost breakdown is shown transparently in every response.*

## MCP Integration

3 MCP tools available via `/smithery`:
- `routenet_route` — route a capability to the best service
- `routenet_simulate` — dry-run routing
- `routenet_strategies` — list strategies

## Deployment

### Render (recommended)
```bash
git clone https://github.com/rplryan/x402-routenet.git
cd x402-routenet
# Push to GitHub, connect Render to this repo
# Or: deploy via render.yaml (starter plan, always-on)
```

### Local
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Relationship to x402 Discovery

| | Discovery | RouteNet |
|---|---|---|
| **Role** | Catalog layer | Execution layer |
| **Question** | "What services exist?" | "Which service should I use?" |
| **Output** | Quality-ranked catalog | Routing decision + cost breakdown |
| **Protocol** | REST + MCP | REST + MCP |

RouteNet queries Discovery internally — no need to query both separately.

## License

MIT
