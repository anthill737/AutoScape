import asyncio
import os
from typing import TypedDict
from urllib.parse import urlparse

import httpx

from app.domain.retailers import APPROVED_RETAILERS
from app.providers.base import MissingApiKeyError, missing_api_key_message

_PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
_PERPLEXITY_MODEL = "sonar"
_SEARCH_PROMPT = (
    "List the best products and materials for a {category} landscaping project. "
    "Include product names, sources, and current prices where available."
)
_APPROVED_RETAILER_DOMAINS = {retailer["domain"] for retailer in APPROVED_RETAILERS}
_APPROVED_RETAILER_SITE_FILTER = (
    "(site:homedepot.com OR site:lowes.com OR site:menards.com OR "
    "site:acehardware.com OR site:costco.com)"
)


class GroundingResult(TypedDict):
    category: str
    urls: list[str]
    snippets: list[str]


class SearchGrounding:
    """Issues one Perplexity sonar search per material category and parses citations."""

    async def search(self, categories: list[str]) -> list[GroundingResult]:
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("PERPLEXITY_API_KEY", "Search Grounding")
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [self._search_one(client, api_key, cat) for cat in categories]
            return list(await asyncio.gather(*tasks))

    async def _search_one(
        self, client: httpx.AsyncClient, api_key: str, category: str
    ) -> GroundingResult:
        payload = {
            "model": _PERPLEXITY_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": _build_query(category),
                }
            ],
            "max_tokens": 400,
            "return_citations": True,
        }
        response = await client.post(
            _PERPLEXITY_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return _parse_response(category, response.json())


def _build_query(category: str) -> str:
    return f"{_SEARCH_PROMPT.format(category=category)} {_APPROVED_RETAILER_SITE_FILTER}"


def _parse_response(category: str, data: dict) -> GroundingResult:
    # Perplexity returns citation URLs in a top-level "citations" list.
    raw_citations = data.get("citations", [])
    urls = [
        c.strip()
        for c in raw_citations
        if isinstance(c, str) and _is_approved_retailer_url(c)
    ]

    # Only include the text snippet when there are citation URLs to back it up.
    # A snippet without citations is ungrounded and not useful for Build Sheet generation.
    snippets: list[str] = []
    if urls:
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content and content.strip():
                snippets = [content.strip()]

    return {"category": category, "urls": urls, "snippets": snippets}


def _is_approved_retailer_url(url: str) -> bool:
    host = urlparse(url.strip()).hostname
    if not host:
        return False

    normalized_host = host.removeprefix("www.").lower()
    return normalized_host in _APPROVED_RETAILER_DOMAINS
