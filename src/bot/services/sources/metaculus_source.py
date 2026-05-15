import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from bot.services.sources._topic_map import METACULUS_CATEGORIES
from bot.services.sources.base import NormalizedMarket, Resolution

logger = logging.getLogger(__name__)

_SOURCE = "metaculus"
_BASE_URL = "https://www.metaculus.com"
_QUESTION_URL = "https://www.metaculus.com/questions/{post_id}/{slug}/"
_MIN_FORECASTERS = 10.0
_TIMEOUT = 30.0
_MAX_RETRIES = 3
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_SEARCH_LIMIT = 100


class MetaculusSource:
    name = _SOURCE
    min_volume = _MIN_FORECASTERS

    def __init__(self, api_token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=_TIMEOUT,
            headers={"Authorization": f"Token {api_token}"},
            transport=httpx.AsyncHTTPTransport(retries=2),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_candidates(self, *, subcategory: str, limit: int) -> list[NormalizedMarket]:
        categories = METACULUS_CATEGORIES.get(subcategory, [])
        searches: list[str | None] = [None]
        for slug in categories[:3]:
            searches.append(slug)

        out: list[NormalizedMarket] = []
        seen: set[int] = set()

        for cat in searches:
            params: dict[str, Any] = {
                "forecast_type": "binary",
                "statuses": "open",
                "with_cp": "true",
                "order_by": "scheduled_close_time",
                "limit": _SEARCH_LIMIT,
            }
            if cat:
                params["categories"] = cat

            try:
                resp = await self._get("/api/posts/", params=params)
            except Exception:
                logger.warning("Metaculus /api/posts/ failed for category=%s", cat)
                continue

            for raw in resp.json().get("results") or []:
                post_id = raw.get("id")
                if not isinstance(post_id, int) or post_id in seen:
                    continue
                seen.add(post_id)

                normalized = _parse_post(raw)
                if not normalized:
                    continue

                out.append(normalized)
                if len(out) >= limit:
                    return out

        return out

    async def get_market(self, source_id: str) -> NormalizedMarket | None:
        try:
            resp = await self._get(f"/api/posts/{source_id}/", params={"with_cp": "true"})
        except Exception:
            logger.warning("Metaculus get_post failed for %s", source_id)

            return None

        return _parse_post(resp.json())

    async def get_probability(self, source_id: str) -> float | None:
        market = await self.get_market(source_id)

        return market.probability if market else None

    async def get_resolution(self, source_id: str) -> Resolution | None:
        market = await self.get_market(source_id)
        if not market or not market.is_resolved:
            return None

        return Resolution(outcome=market.resolution or "CANCEL", resolved_at=market.resolution_time)

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
                logger.warning("Metaculus %s returned %d, retrying in %.1fs", url, resp.status_code, delay)
                await asyncio.sleep(min(delay, 30))

        last_resp.raise_for_status()  # type: ignore[union-attr]

        return last_resp  # type: ignore[return-value]


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


def _extract_probability(question: dict) -> float | None:
    agg = (question.get("aggregations") or {}).get("recency_weighted") or {}
    latest = agg.get("latest")
    if not latest:
        return None

    values = latest.get("forecast_values")
    if not isinstance(values, list) or len(values) != 2:
        return None

    try:
        return float(values[1])
    except (TypeError, ValueError):
        return None


def _map_resolution(question_resolution: Any) -> str | None:
    if question_resolution is None:
        return None
    text = str(question_resolution).strip().lower()
    if text == "yes":
        return "YES"
    if text == "no":
        return "NO"
    if text in {"ambiguous", "annulled"}:
        return "CANCEL"

    return "CANCEL"


def _collect_tags(post: dict) -> list[str]:
    out: list[str] = []
    projects = post.get("projects") or {}
    for key in ("category", "tag", "topic"):
        for item in projects.get(key) or []:
            slug = item.get("slug")
            if slug:
                out.append(str(slug).lower())

    return list(dict.fromkeys(out))


def _parse_post(post: dict) -> NormalizedMarket | None:
    post_id = post.get("id")
    if not isinstance(post_id, int):
        return None

    question = post.get("question") or {}
    if question.get("type") != "binary":
        return None

    probability = _extract_probability(question)
    if probability is None:
        return None

    close_dt = _parse_dt(post.get("scheduled_close_time") or question.get("scheduled_close_time"))
    if not close_dt:
        return None

    forecasters = post.get("nr_forecasters") or 0
    try:
        volume = float(forecasters)
    except (TypeError, ValueError):
        volume = 0.0

    slug = post.get("slug") or ""
    url = _QUESTION_URL.format(post_id=post_id, slug=slug)

    q_status = (question.get("status") or post.get("status") or "").lower()
    is_resolved = bool(post.get("resolved") or q_status == "resolved")
    resolution = _map_resolution(question.get("resolution")) if is_resolved else None
    resolution_time = _parse_dt(
        question.get("actual_resolve_time") or post.get("actual_resolve_time")
    ) if is_resolved else None

    return NormalizedMarket(
        source=_SOURCE,
        source_id=str(post_id),
        question=post.get("title", ""),
        url=url,
        probability=probability,
        volume=volume,
        close_time=close_dt,
        is_resolved=is_resolved,
        resolution=resolution,
        resolution_time=resolution_time,
        tags=_collect_tags(post),
    )
