import logging
from datetime import datetime, timezone

from bot.services.manifold import ManifoldClient
from bot.services.sources._topic_map import MANIFOLD_TOPICS
from bot.services.sources.base import NormalizedMarket, Resolution

logger = logging.getLogger(__name__)

_SOURCE = "manifold"
_MIN_MANA_VOLUME = 100.0
_SEARCH_LIMIT = 100


class ManifoldSource:
    name = _SOURCE
    min_volume = _MIN_MANA_VOLUME

    def __init__(self, client: ManifoldClient | None = None) -> None:
        self._client = client or ManifoldClient()

    async def close(self) -> None:
        await self._client.close()

    async def fetch_candidates(self, *, subcategory: str, limit: int) -> list[NormalizedMarket]:
        topic_slugs = MANIFOLD_TOPICS.get(subcategory, [])
        searches: list[str | None] = [None]
        for slug in topic_slugs[:3]:
            searches.append(slug)

        out: list[NormalizedMarket] = []
        seen: set[str] = set()

        for topic in searches:
            try:
                markets = await self._client.search_markets(
                    sort="close-date", limit=_SEARCH_LIMIT, topic_slug=topic,
                )
            except Exception:
                logger.warning("Manifold search_markets failed for topic=%s", topic)
                continue

            for m in markets:
                if m.id in seen:
                    continue
                seen.add(m.id)

                close_dt = _from_ms(m.close_time)
                if not close_dt:
                    continue

                normalized = NormalizedMarket(
                    source=_SOURCE,
                    source_id=m.id,
                    question=m.question,
                    url=m.url,
                    probability=m.probability,
                    volume=m.volume,
                    close_time=close_dt,
                    is_resolved=m.is_resolved,
                    resolution=m.resolution,
                    resolution_time=_from_ms(m.resolution_time) if m.resolution_time else None,
                    tags=[s.lower() for s in m.group_slugs],
                )
                out.append(normalized)

                if len(out) >= limit:
                    return out

        return out

    async def get_market(self, source_id: str) -> NormalizedMarket | None:
        try:
            data = await self._client.get_market(source_id)
        except Exception:
            logger.warning("Manifold get_market failed for %s", source_id)

            return None

        close_dt = _from_ms(data.get("closeTime") or 0)
        if not close_dt:
            return None

        return NormalizedMarket(
            source=_SOURCE,
            source_id=data["id"],
            question=data.get("question", ""),
            url=data.get("url", ""),
            probability=float(data.get("probability", 0.5)),
            volume=float(data.get("volume", 0) or 0),
            close_time=close_dt,
            is_resolved=bool(data.get("isResolved", False)),
            resolution=data.get("resolution"),
            resolution_time=_from_ms(data.get("resolutionTime") or 0),
            tags=[s.lower() for s in data.get("groupSlugs", []) or []],
        )

    async def get_probability(self, source_id: str) -> float | None:
        try:
            return await self._client.get_prob(source_id)
        except Exception:
            logger.warning("Manifold get_prob failed for %s", source_id)

            return None

    async def get_resolution(self, source_id: str) -> Resolution | None:
        try:
            market = await self._client.get_market(source_id)
        except Exception:
            logger.warning("Manifold get_market (for resolution) failed for %s", source_id)

            return None

        if not market.get("isResolved"):
            return None

        raw = market.get("resolution")
        outcome = raw if raw in ("YES", "NO") else "CANCEL"
        resolved_at = _from_ms(market.get("resolutionTime") or 0)

        return Resolution(outcome=outcome, resolved_at=resolved_at)


def _from_ms(ms: int | float | None) -> datetime | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None
