import logging

from bot.config import settings
from bot.services.sources.base import MarketSource, NormalizedMarket, Resolution

logger = logging.getLogger(__name__)


class SourcesRegistry:
    """Holds active market sources and dispatches by source name."""

    def __init__(self, sources: list[MarketSource]) -> None:
        self._sources: dict[str, MarketSource] = {s.name: s for s in sources}

    def get(self, name: str) -> MarketSource | None:
        return self._sources.get(name)

    def require(self, name: str) -> MarketSource:
        src = self._sources.get(name)
        if not src:
            raise KeyError(f"Source {name!r} is not registered")

        return src

    def all(self) -> list[MarketSource]:
        return list(self._sources.values())

    def names(self) -> list[str]:
        return list(self._sources.keys())

    async def close_all(self) -> None:
        for src in self._sources.values():
            try:
                await src.close()
            except Exception:
                logger.exception("Failed to close source %s", src.name)


def build_registry() -> SourcesRegistry:
    """Construct the registry with all sources that have credentials available."""
    from bot.services.sources.manifold_source import ManifoldSource
    from bot.services.sources.polymarket_source import PolymarketSource

    sources: list[MarketSource] = [ManifoldSource(), PolymarketSource()]

    if settings.metaculus_api_token:
        from bot.services.sources.metaculus_source import MetaculusSource
        sources.append(MetaculusSource(settings.metaculus_api_token))
    else:
        logger.info("METACULUS_API_TOKEN not set — Metaculus source disabled")

    logger.info("Active market sources: %s", [s.name for s in sources])

    return SourcesRegistry(sources)


__all__ = [
    "MarketSource",
    "NormalizedMarket",
    "Resolution",
    "SourcesRegistry",
    "build_registry",
]
