import logging

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def translate_to_russian(text: str) -> str | None:
    if not settings.openrouter_api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _OPENROUTER_URL,
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json={
                    "model": settings.openrouter_model,
                    "max_tokens": 200,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Translate the following prediction market question to Russian. "
                                "Keep it concise and natural. Return only the translation, nothing else. "
                                "If the text is already in Russian, return it as-is."
                            ),
                        },
                        {"role": "user", "content": text},
                    ],
                },
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip()
            if result:
                return result
    except Exception:
        logger.exception("Translation failed")

    return None
