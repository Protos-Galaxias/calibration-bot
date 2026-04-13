import asyncio
import logging
from typing import Any

import httpx

from bot.models.question import LiteMarket

logger = logging.getLogger(__name__)

BASE_URL = "https://api.manifold.markets"
_TIMEOUT = 30.0
_MAX_RETRIES = 3
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class ManifoldClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=_TIMEOUT,
            transport=httpx.AsyncHTTPTransport(retries=2),
        )

    async def close(self) -> None:
        await self._client.aclose()

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
                logger.warning("Manifold %s returned %d, retrying in %.1fs", url, resp.status_code, delay)
                await asyncio.sleep(min(delay, 30))

        last_resp.raise_for_status()  # type: ignore[union-attr]

        return last_resp  # type: ignore[return-value]

    async def search_markets(
        self,
        *,
        term: str = "",
        filter: str = "open",
        contract_type: str = "BINARY",
        sort: str = "liquidity",
        limit: int = 50,
        topic_slug: str | None = None,
    ) -> list[LiteMarket]:
        params: dict[str, Any] = {
            "term": term,
            "filter": filter,
            "contractType": contract_type,
            "sort": sort,
            "limit": limit,
        }
        if topic_slug:
            params["topicSlug"] = topic_slug

        resp = await self._get("/v0/search-markets", params=params)

        return [LiteMarket.from_api(m) for m in resp.json()]

    async def get_market(self, market_id: str) -> dict:
        resp = await self._get(f"/v0/market/{market_id}")

        return resp.json()

    async def get_prob(self, market_id: str) -> float:
        resp = await self._get(f"/v0/market/{market_id}/prob")
        data = resp.json()

        return float(data.get("prob", data) if isinstance(data, dict) else data)
