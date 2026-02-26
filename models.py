from pydantic import BaseModel, Field
from typing import Optional, Any


class RouteFilter(BaseModel):
    """Optional filters applied before routing strategy."""
    max_price: Optional[float] = Field(None, description="Max service price in USD")
    min_uptime: Optional[float] = Field(None, description="Min uptime % (0-100)")
    category: Optional[str] = Field(None, description="Service category: data, compute, research, agent, utility")
    min_trust_score: Optional[float] = Field(None, description="Min ERC-8004 trust score (0-100)")


class RouteRequest(BaseModel):
    """Request body for POST /route."""
    capability: str = Field(..., description="What you need, e.g. 'web scraping', 'image generation'")
    input: Optional[dict[str, Any]] = Field(None, description="Input to pass to the service (v2: will be forwarded)")
    strategy: str = Field("best", description="Routing strategy: best | cheapest | fastest | custom")
    filter: Optional[RouteFilter] = Field(None, description="Optional filters")


class CostBreakdown(BaseModel):
    """Pricing Model 3 cost breakdown."""
    service_price_usd: float
    routing_fee_usd: float      # $0.0002 flat fee per route
    settlement_fee_usd: float   # 0.5% of service_price_usd
    total_usd: float


class QualitySignals(BaseModel):
    """Quality signals from the Discovery API + ERC-8004."""
    uptime_pct: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    trust_score: Optional[float] = None      # ERC-8004 reputation (0-100)
    health_status: str = "unverified"
    erc8004_verified: bool = False
