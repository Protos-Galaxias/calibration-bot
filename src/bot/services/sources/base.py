from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class NormalizedMarket:
    source: str
    source_id: str
    question: str
    url: str
    probability: float
    volume: float
    close_time: datetime
    is_resolved: bool = False
    resolution: str | None = None
    resolution_time: datetime | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Resolution:
    """Outcome of a resolved market.

    `outcome` is one of "YES", "NO", or "CANCEL" (anything ambiguous/annulled).
    """

    outcome: str
    resolved_at: datetime | None = None


@runtime_checkable
class MarketSource(Protocol):
    """Common interface every market data source implements."""

    name: str
    min_volume: float

    async def fetch_candidates(
        self,
        *,
        subcategory: str,
        limit: int,
    ) -> list[NormalizedMarket]:
        """Return candidate open binary markets relevant to the given subcategory."""
        ...

    async def get_market(self, source_id: str) -> NormalizedMarket | None:
        """Fetch a single market by its source-native id; None on error."""
        ...

    async def get_probability(self, source_id: str) -> float | None:
        """Cheap call to fetch only the current implied probability; None on error."""
        ...

    async def get_resolution(self, source_id: str) -> Resolution | None:
        """Return the resolution if the market has resolved, otherwise None."""
        ...

    async def close(self) -> None:
        ...
