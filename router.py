"""
Routing logic: strategies, scoring, and cost calculation.

Pricing Model 3 (TODO: finalize exact values before v2 launch):
  ROUTING_FEE_USD  = $0.0002 flat per routing decision
  SETTLEMENT_PCT   = 0.5% of the service price on execution
These fees are tracked in every response but NOT yet collected
(no wallet configured). Set ROUTENET_WALLET env var to enable collection.
"""
from typing import Optional
from models import RouteFilter, CostBreakdown, QualitySignals

# ---------------------------------------------------------------------------
# Pricing Model 3 constants
# TODO: REVISIT BEFORE LAUNCH — exact values pending owner approval
# ---------------------------------------------------------------------------
ROUTING_FEE_USD = 0.0002    # flat fee per routing decision
SETTLEMENT_PCT  = 0.005     # 0.5% of service price on execution

# Composite score weights for "best" strategy
WEIGHT_UPTIME   = 0.4
WEIGHT_LATENCY  = 0.3
WEIGHT_TRUST    = 0.3

# Services below this uptime threshold are excluded from routing
MIN_HEALTHY_UPTIME = 80.0
MAX_LATENCY_NORM   = 1000.0  # latency cap for normalization (ms)

# Strategy descriptions (also exported for API)
STRATEGIES_DATA = [
    {
        "name": "best",
        "description": "Composite quality score: uptime (40%) + speed (30%) + ERC-8004 trust (30%)",
        "formula": "(uptime_pct/100)*0.4 + (1 - min(latency_ms/1000,1))*0.3 + (trust_score/100 if available else 0.5)*0.3",
        "use_case": "Best overall reliability. Recommended default.",
    },
    {
        "name": "cheapest",
        "description": "Lowest service price among healthy services (uptime > 80%)",
        "formula": "sort by price_usd ascending; filter uptime > 80%",
        "use_case": "Cost-sensitive agents running at scale.",
    },
    {
        "name": "fastest",
        "description": "Lowest average latency among healthy services",
        "formula": "sort by avg_latency_ms ascending; filter uptime > 80%",
        "use_case": "Latency-sensitive real-time applications.",
    },
    {
        "name": "custom",
        "description": "Filter by max_price, min_uptime, category, min_trust_score; then apply best composite scoring",
        "formula": "apply filters, then best composite on remaining",
        "use_case": "Fine-grained control over service selection criteria.",
    },
]


def _composite_score(svc: dict) -> float:
    """Compute the 'best' composite score for a service."""
    uptime = float(svc.get("uptime_pct") or 70.0)
    latency = float(svc.get("avg_latency_ms") or 500.0)
    trust_raw = svc.get("erc8004_reputation_score") or svc.get("trust_score")
    trust = float(trust_raw) / 100.0 if trust_raw is not None else 0.5

    return (
        (uptime / 100.0) * WEIGHT_UPTIME
        + (1.0 - min(latency / MAX_LATENCY_NORM, 1.0)) * WEIGHT_LATENCY
        + trust * WEIGHT_TRUST
    )


def _is_healthy(svc: dict, min_uptime: float = MIN_HEALTHY_UPTIME) -> bool:
    """Return True if the service meets the minimum uptime threshold."""
    status = svc.get("health_status", "") or ""
    if status == "unhealthy":
        return False
    uptime = svc.get("uptime_pct")
    if uptime is None:
        return True  # unverified: assume ok
    return float(uptime) >= min_uptime


def rank_services(
    services: list[dict],
    strategy: str = "best",
    filt: Optional[RouteFilter] = None,
) -> tuple[list[dict], str]:
    """
    Rank services by strategy. Returns (ranked_list, reason_string).
    Applies optional filters before ranking.
    """
    candidates = list(services)

    # Apply filters
    if filt:
        if filt.max_price is not None:
            candidates = [s for s in candidates if float(s.get("price_usd") or 0) <= filt.max_price]
        if filt.min_uptime is not None:
            candidates = [s for s in candidates if _is_healthy(s, min_uptime=filt.min_uptime)]
        elif strategy in ("cheapest", "fastest", "best"):
            candidates = [s for s in candidates if _is_healthy(s)]
        if filt.category:
            cat_filter = filt.category.lower()
            candidates = [s for s in candidates if (s.get("category") or "").lower() == cat_filter]
        if filt.min_trust_score is not None:
            candidates = [
                s for s in candidates
                if float(s.get("erc8004_reputation_score") or s.get("trust_score") or 0) >= filt.min_trust_score
            ]
    else:
        # Always filter unhealthy for non-custom strategies
        if strategy in ("cheapest", "fastest", "best"):
            candidates = [s for s in candidates if _is_healthy(s)]

    if not candidates:
        return [], "No services match the criteria"

    if strategy == "cheapest":
        ranked = sorted(candidates, key=lambda s: float(s.get("price_usd") or 9999))
        winner = ranked[0]
        reason = f"Cheapest healthy service: {winner.get('name')} at ${float(winner.get('price_usd') or 0):.4f}/call"

    elif strategy == "fastest":
        ranked = sorted(candidates, key=lambda s: float(s.get("avg_latency_ms") or 9999))
        winner = ranked[0]
        reason = f"Fastest healthy service: {winner.get('name')} at {float(winner.get('avg_latency_ms') or 0):.0f}ms avg"

    elif strategy in ("best", "custom"):
        ranked = sorted(candidates, key=_composite_score, reverse=True)
        winner = ranked[0]
        score = _composite_score(winner)
        reason = (
            f"Best composite score {score:.3f}: {winner.get('name')} "
            f"(uptime={winner.get('uptime_pct')}%, latency={winner.get('avg_latency_ms')}ms)"
        )

    else:
        return [], f"Unknown strategy: {strategy!r}"

    return ranked, reason


def compute_cost(service_price_usd: float) -> CostBreakdown:
    """
    Calculate Pricing Model 3 cost breakdown.
    TODO: REVISIT before launch — exact fee amounts pending owner approval.
    """
    settlement = round(service_price_usd * SETTLEMENT_PCT, 8)
    total = round(service_price_usd + ROUTING_FEE_USD + settlement, 8)
    return CostBreakdown(
        service_price_usd=round(service_price_usd, 8),
        routing_fee_usd=ROUTING_FEE_USD,
        settlement_fee_usd=settlement,
        total_usd=total,
    )


def extract_quality(svc: dict) -> QualitySignals:
    """Extract quality signals from a service record."""
    trust_raw = svc.get("erc8004_reputation_score") or svc.get("trust_score")
    return QualitySignals(
        uptime_pct=svc.get("uptime_pct"),
        avg_latency_ms=svc.get("avg_latency_ms"),
        trust_score=float(trust_raw) if trust_raw is not None else None,
        health_status=svc.get("health_status") or "unverified",
        erc8004_verified=bool(svc.get("erc8004_verified")),
    )
