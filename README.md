# x402 RouteNet

> Intelligent routing for x402 micropayments — multi-provider fallback, latency-based selection, automatic failover.

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Network: Base](https://img.shields.io/badge/network-Base-0052FF.svg)](https://base.org)
[![Live on Render](https://img.shields.io/badge/live-render.com-46E3B7.svg)](https://x402-routenet.onrender.com)

**Live API:** https://x402-routenet.onrender.com

RouteNet is the routing layer for x402 payment infrastructure. Instead of hardcoding a single payment facilitator, your application routes through RouteNet and gets intelligent provider selection based on cost, speed, reliability, or load distribution — with automatic failover when any individual provider is unavailable.

---

## Quick Start

```bash
# Check service health
curl https://x402-routenet.onrender.com/health

# Route a payment request to the optimal provider
curl -X POST https://x402-routenet.onrender.com/route \
  -H "Content-Type: application/json" \
  -d '{
    "service_url": "https://example.com/api",
    "strategy": "fastest",
    "network": "base-mainnet"
  }'
```

---

## Routing Strategies

| Strategy | Description | Best For |
|---|---|---|
| `cheapest` | Selects the provider with the lowest USDC fee | Cost-sensitive or high-volume applications |
| `fastest` | Minimizes latency based on rolling response time history | Real-time or user-facing applications |
| `most_reliable` | Prefers providers with the highest historical success rate | Mission-critical payment flows |
| `load_balanced` | Distributes traffic evenly across all healthy providers | Applications with variable or bursty traffic |

---

## API Reference

### `POST /route`

Route a request to the optimal provider based on your chosen strategy.

```json
POST https://x402-routenet.onrender.com/route
{
  "service_url": "https://example.com/api",
  "strategy": "fastest",
  "network": "base-mainnet"
}
```

**Response:**

```json
{
  "routed_to": "https://provider-a.example.com/api",
  "strategy_used": "fastest",
  "estimated_latency_ms": 45,
  "fallback_available": true,
  "provider_id": "provider-a"
}
```

### `GET /health`

```bash
curl https://x402-routenet.onrender.com/health
# {"status": "ok", "version": "1.0.0", "providers_online": 3}
```

### `GET /providers`

Returns all registered providers with their current status, latency history, and success rates.

```bash
curl https://x402-routenet.onrender.com/providers
```

### `POST /providers/register`

Register a new x402 provider endpoint with RouteNet.

```json
POST https://x402-routenet.onrender.com/providers/register
{
  "name": "my-facilitator",
  "url": "https://my-facilitator.example.com",
  "network": "base-mainnet",
  "fee_usdc": 0.001
}
```

---

## Why Routing Matters

The x402 protocol enables HTTP-native micropayments, but production deployments face a fundamental reliability problem: **a single facilitator is a single point of failure.**

When a payment facilitator goes down, every payment routed through it fails — often silently from the end user's perspective. For applications where payment success equals functionality, this is not acceptable.

RouteNet addresses this directly:

- **Monitors** all registered providers continuously via background health checks
- **Detects** degraded or failed providers before they affect your users
- **Routes around** unavailable providers automatically, without client changes
- **Selects** the best available provider based on your chosen strategy
- **Tracks** per-provider success rates, latency, and cost to inform routing decisions over time

For production x402 applications, the difference between a hardcoded single endpoint and intelligent routing is the difference between a brittle demo and a system your users can depend on.

---

## Integration Example

```python
import requests
from x402_harness import X402Client  # pip install x402-payment-harness

def make_x402_payment(service_url: str, strategy: str = "most_reliable") -> dict:
    # Ask RouteNet for the optimal provider
    route_response = requests.post(
        "https://x402-routenet.onrender.com/route",
        json={
            "service_url": service_url,
            "strategy": strategy,
            "network": "base-mainnet"
        }
    ).json()

    routed_url = route_response["routed_to"]

    # Use the routed URL with the x402 Payment Harness
    client = X402Client(private_key="0xYOUR_PRIVATE_KEY")
    return client.get(routed_url)
```

---

## Architecture

```
  Your Application
        │
        ▼
  ┌─────────────┐     ┌──────────────────────┐
  │  x402       │◄────│  Health Monitor      │
  │  RouteNet   │     │  (background polling)│
  └──────┬──────┘     └──────────────────────┘
         │
         ▼
  ┌─────────────────────────────────┐
  │  Strategy Engine                │
  │  cheapest / fastest /           │
  │  most_reliable / load_balanced  │
  └──────────────┬──────────────────┘
                 │
         ┌───────┼───────┐
         ▼       ▼       ▼
    Provider  Provider  Provider
       A        B        C
   (healthy) (healthy) (degraded → skipped)
```

---

## Self-Hosting

RouteNet is a standard FastAPI application. Deploy anywhere that runs Python:

```bash
git clone https://github.com/rplryan/x402-routenet
cd x402-routenet
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Configuration via environment variables:

| Variable | Description | Default |
|---|---|---|
| `PORT` | Port to listen on | `8000` |
| `HEALTH_CHECK_INTERVAL` | Seconds between provider health checks | `30` |
| `LATENCY_WINDOW` | Number of recent requests used for latency averaging | `10` |

---

## Part of the x402 Infrastructure Suite

RouteNet is part of a set of tools built to make x402 production-ready for developers:

| Tool | What It Does | Status |
|---|---|---|
| **x402 Payment Harness** | EOA-based client library and CLI for testing x402 | [PyPI + GitHub](https://github.com/rplryan/x402-payment-harness) |
| **x402 Discovery API** | Searchable registry of live x402-enabled services | [Live on Render](https://github.com/rplryan/x402-discovery-api) |
| **x402 RouteNet** | Intelligent routing with multi-provider fallback | This repo |

Together, these tools cover the three layers a production x402 stack needs: **find** services (Discovery API), **route** payments reliably (RouteNet), and **test** the full client flow (Payment Harness).

---

## Version History

| Version | Changes |
|---|---|
| 1.0.0 | Initial release: 4 routing strategies, background health monitoring, provider registry, REST API |

---

## License

MIT © 2024 rplryan
