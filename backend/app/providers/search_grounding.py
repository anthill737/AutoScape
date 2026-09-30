"""Web-grounded product research via the Perplexity Agent API.

Perplexity retired the Sonar Chat Completions endpoint on 2026-09-27. The Agent API
(``POST /v1/agent``) replaces it: the model is chosen with a ``provider/model`` id,
web search is an explicit tool with a domain allowlist, and sources come back as a
``search_results`` output item plus ``url_citation`` annotations on the answer text.
"""

from __future__ import annotations

import asyncio
import os
from typing import TypedDict
from urllib.parse import urlparse

import httpx

from app.domain.retailers import APPROVED_RETAILERS
from app.providers.base import MissingApiKeyError, missing_api_key_message
from app.providers.model_catalog import default_model_for

PERPLEXITY_AGENT_URL = "https://api.perplexity.ai/v1/agent"
_DEFAULT_MODEL = default_model_for("perplexity")
_MAX_OUTPUT_TOKENS = 500
_MAX_RESULTS = 10

_INSTRUCTIONS = (
    "You are a landscaping materials researcher. Answer with a concise list of specific "
    "products and materials, with product names and current prices where available. "
    "Only use the retailer sites you are allowed to search."
)
_SEARCH_PROMPT = (
    "List the best products and materials for a {category} landscaping project. "
    "Include product names, sources, and current prices where available."
)
_APPROVED_RETAILER_DOMAINS = {retailer["domain"] for retailer in APPROVED_RETAILERS}
# Agent API domain allowlist: bare hostnames, max 20 entries.
_SEARCH_DOMAIN_FILTER = [retailer["domain"] for retailer in APPROVED_RETAILERS]


class GroundingResult(TypedDict):
    category: str
    urls: list[str]
    snippets: list[str]


class SearchGrounding:
    """Issues one Agent API search per material category and parses the sources."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or _DEFAULT_MODEL

    async def search(self, categories: list[str]) -> list[GroundingResult]:
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("PERPLEXITY_API_KEY", "Search Grounding")
            )

        async with httpx.AsyncClient(timeout=60.0) as client:
            tasks = [self._search_one(client, api_key, cat) for cat in categories]
            return list(await asyncio.gather(*tasks))

    async def _search_one(
        self, client: httpx.AsyncClient, api_key: str, category: str
    ) -> GroundingResult:
        response = await client.post(
            PERPLEXITY_AGENT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=build_payload(category, self.model),
        )
        response.raise_for_status()
        return _parse_response(category, response.json())


def build_payload(category: str, model: str = _DEFAULT_MODEL) -> dict:
    return {
        "model": model,
        "instructions": _INSTRUCTIONS,
        "input": _build_query(category),
        # Required for anthropic/* models on the Agent API; harmless elsewhere.
        "max_output_tokens": _MAX_OUTPUT_TOKENS,
        "tools": [
            {
                "type": "web_search",
                "max_results": _MAX_RESULTS,
                "filters": {"search_domain_filter": _SEARCH_DOMAIN_FILTER},
            }
        ],
    }


def _build_query(category: str) -> str:
    return _SEARCH_PROMPT.format(category=category)


def _parse_response(category: str, data: dict) -> GroundingResult:
    urls: list[str] = []
    text_parts: list[str] = []

    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "search_results":
            for result in item.get("results", []) or []:
                url = result.get("url") if isinstance(result, dict) else None
                if isinstance(url, str) and _is_approved_retailer_url(url):
                    urls.append(url.strip())
        elif item_type == "message":
            for part in item.get("content", []) or []:
                if not isinstance(part, dict) or part.get("type") != "output_text":
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
                for annotation in part.get("annotations", []) or []:
                    if not isinstance(annotation, dict):
                        continue
                    if annotation.get("type") != "url_citation":
                        continue
                    url = annotation.get("url")
                    if isinstance(url, str) and _is_approved_retailer_url(url):
                        urls.append(url.strip())

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique_urls = [u for u in urls if not (u in seen or seen.add(u))]

    # Only include the text snippet when there are citation URLs to back it up.
    # A snippet without citations is ungrounded and not useful for Build Sheet generation.
    snippets = ["\n".join(text_parts)] if unique_urls and text_parts else []

    return {"category": category, "urls": unique_urls, "snippets": snippets}


def _is_approved_retailer_url(url: str) -> bool:
    host = urlparse(url.strip()).hostname
    if not host:
        return False

    normalized_host = host.removeprefix("www.").lower()
    return normalized_host in _APPROVED_RETAILER_DOMAINS
