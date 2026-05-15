import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from bot.services.sources._topic_map import POLYMARKET_TAGS
from bot.services.sources.base import NormalizedMarket, Resolution

logger = logging.getLogger(__name__)

_SOURCE = "polymarket"
_BASE_URL = "https://gamma-api.polymarket.com"
_MARKET_URL = "https://polymarket.com/market/{slug}"
_MIN_USD_VOLUME = 1000.0
_TIMEOUT = 30.0
_MAX_RETRIES = 3
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_SEARCH_LIMIT = 100


class PolymarketSource:
    name = _SOURCE
    min_volume = _MIN_USD_VOLUME

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=_TIMEOUT,
            transport=httpx.AsyncHTTPTransport(retries=2),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_candidates(self, *, subcategory: str, limit: int) -> list[NormalizedMarket]:
        tag_slugs = POLYMARKET_TAGS.get(subcategory, [])
        searches: list[str | None] = [None]
        for slug in tag_slugs[:3]:
            searches.append(slug)

        out: list[NormalizedMarket] = []
        seen: set[str] = set()

        for tag in searches:
            params: dict[str, Any] = {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "limit": _SEARCH_LIMIT,
                "order": "endDate",
                "ascending": "true",
            }
            if tag:
                params["tag_slug"] = tag

            try:
                resp = await self._get("/markets", params=params)
            except Exception:
                logger.warning("Polymarket /markets failed for tag=%s", tag)
                continue

            for raw in resp.json():
                source_id = str(raw.get("id") or raw.get("conditionId") or "")
                if not source_id or source_id in seen:
                    continue
                seen.add(source_id)

                normalized = _parse_market(raw)
                if not normalized:
                    continue

                out.append(normalized)
                if len(out) >= limit:
                    return out

        return out

    async def get_market(self, source_id: str) -> NormalizedMarket | None:
        try:
            resp = await self._get(f"/markets/{source_id}")
        except Exception:
            logger.warning("Polymarket get_market failed for %s", source_id)

            return None

        data = resp.json()
        if isinstance(data, list):
            data = data[0] if data else None
        if not data:
            return None

        return _parse_market(data)

    async def get_probability(self, source_id: str) -> float | None:
        market = await self.get_market(source_id)

        return market.probability if market else None

    async def get_resolution(self, source_id: str) -> Resolution | None:
        market = await self.get_market(source_id)
        if not market:
            return None
        if not market.is_resolved:
            return None

        outcome = market.resolution or "CANCEL"

        return Resolution(outcome=outcome, resolved_at=market.resolution_time)

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        last_resp: httpx.Response | None = None
        for attempt in range(_MAX_RETRIES):
            resp = await self._client.get(url, **kwargs)
            if resp.status_code not in _RETRY_STATUSES:
                resp.raise_for_status()

                return resp

            last_resp = resp
            if attempt < _MAX_RETRIES - 1:
                delay = float(resp.headers.get("Retry-After", str(2 ** attempt)))
                logger.warning("Polymarket %s returned %d, retrying in %.1fs", url, resp.status_code, delay)
                await asyncio.sleep(min(delay, 30))

        last_resp.raise_for_status()  # type: ignore[union-attr]

        return last_resp  # type: ignore[return-value]


def _parse_json_field(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
            if isinstance(value, list):
                return value
        except (ValueError, TypeError):
            return []

    return []


def _parse_dt(raw: Any) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    text = str(raw).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def _yes_index(outcomes: list[str]) -> int | None:
    """Return index of the Yes outcome, or None if not a binary Yes/No market."""
    if len(outcomes) != 2:
        return None
    lowered = [str(o).strip().lower() for o in outcomes]
    if "yes" in lowered and "no" in lowered:
        return lowered.index("yes")

    return None


def _resolution_from_prices(prices: list[Any], yes_idx: int) -> str | None:
    try:
        floats = [float(p) for p in prices]
    except (TypeError, ValueError):
        return None

    if len(floats) != 2:
        return None

    yes_p, no_p = floats[yes_idx], floats[1 - yes_idx]
    if yes_p == 1.0 and no_p == 0.0:
        return "YES"
    if yes_p == 0.0 and no_p == 1.0:
        return "NO"

    return "CANCEL"


def _collect_tags(raw: dict) -> list[str]:
    tags: list[str] = []
    for ev in raw.get("events") or []:
        slug = ev.get("slug")
        if slug:
            tags.append(str(slug).lower())
        ticker = ev.get("ticker")
        if ticker:
            tags.append(str(ticker).lower())
        for series in ev.get("series") or []:
            ss = series.get("slug")
            if ss:
                tags.append(str(ss).lower())

    return list(dict.fromkeys(tags))


def _parse_market(raw: dict) -> NormalizedMarket | None:
    source_id = str(raw.get("id") or raw.get("conditionId") or "")
    if not source_id:
        return None

    outcomes = [str(o) for o in _parse_json_field(raw.get("outcomes"))]
    yes_idx = _yes_index(outcomes)
    if yes_idx is None:
        return None

    prices_raw = _parse_json_field(raw.get("outcomePrices"))
    if len(prices_raw) != 2:
        return None
    try:
        probability = float(prices_raw[yes_idx])
    except (TypeError, ValueError):
        return None

    close_dt = _parse_dt(raw.get("endDate") or raw.get("endDateIso"))
    if not close_dt:
        return None

    volume_num = raw.get("volumeNum")
    try:
        volume = float(volume_num) if volume_num is not None else float(raw.get("volume", 0) or 0)
    except (TypeError, ValueError):
        volume = 0.0

    closed = bool(raw.get("closed"))
    uma_status = str(raw.get("umaResolutionStatus") or "").lower()
    is_resolved = closed and uma_status == "resolved"

    resolution: str | None = None
    resolution_time: datetime | None = None
    if is_resolved:
        resolution = _resolution_from_prices(prices_raw, yes_idx)
        resolution_time = _parse_dt(raw.get("closedTime") or raw.get("umaEndDate") or raw.get("updatedAt"))

    slug = raw.get("slug") or ""
    url = _MARKET_URL.format(slug=slug) if slug else f"https://polymarket.com/{source_id}"

    return NormalizedMarket(
        source=_SOURCE,
        source_id=source_id,
        question=raw.get("question", ""),
        url=url,
        probability=probability,
        volume=volume,
        close_time=close_dt,
        is_resolved=is_resolved,
        resolution=resolution,
        resolution_time=resolution_time,
        tags=_collect_tags(raw),
    )
