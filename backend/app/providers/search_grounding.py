"""Web-grounded product research via the Perplexity Agent API.

Perplexity retired the Sonar Chat Completions endpoint on 2026-09-27. The Agent API
(``POST /v1/agent``) replaces it: the model is chosen with a ``provider/model`` id,
web search is an explicit tool with a domain allowlist, and sources come back as a
``search_results`` output item plus ``url_citation`` annotations on the answer text.

The Agent API is rate limited per second (1 request/s on the base tier), so category
searches run with limited concurrency and retry on 429 / 5xx honouring ``Retry-After``.
"""

from __future__ import annotations

import asyncio
import os
from typing import TypedDict
from urllib.parse import urlparse

import httpx

from app.domain.retailers import APPROVED_RETAILERS, approved_domains
from app.domain.spaces import SpaceConfig, get_space
from app.providers.base import MissingApiKeyError, missing_api_key_message
from app.providers.model_catalog import default_model_for

PERPLEXITY_AGENT_URL = "https://api.perplexity.ai/v1/agent"
_DEFAULT_MODEL = default_model_for("perplexity")
_MAX_OUTPUT_TOKENS = 1200
_MAX_RESULTS = 10
# Base-tier Agent API limit is 1 request/second; two in flight with retries is safe.
_MAX_CONCURRENCY = 2
_MAX_ATTEMPTS = 4
_RETRY_BASE_SECONDS = 1.5
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

# Agent API domain allowlist: bare hostnames, max 20 entries.
_MAX_DOMAIN_FILTER = 20

# Exterior defaults, kept for callers that import the constants. The per-space text and
# domains come from SpaceConfig (app.domain.spaces).
_INSTRUCTIONS = get_space("exterior").search_instructions
_SEARCH_PROMPT = get_space("exterior").search_query_template
_APPROVED_RETAILER_DOMAINS = approved_domains(APPROVED_RETAILERS)
_SEARCH_DOMAIN_FILTER = [retailer["domain"] for retailer in APPROVED_RETAILERS]


class GroundingResult(TypedDict):
    category: str
    urls: list[str]
    snippets: list[str]


class SearchGroundingError(Exception):
    """Perplexity rejected the request; message carries the vendor's own explanation."""

    def __init__(self, status_code: int, model: str, vendor_message: str) -> None:
        self.status_code = status_code
        self.model = model
        self.vendor_message = vendor_message
        super().__init__(
            f"Perplexity Agent API returned HTTP {status_code} for model {model}: "
            f"{vendor_message}"
        )


class SearchGrounding:
    """Issues one Agent API search per material category and parses the sources."""

    def __init__(
        self,
        model: str | None = None,
        space: SpaceConfig | None = None,
        room_type: str | None = None,
    ) -> None:
        self.model = model or _DEFAULT_MODEL
        self.space = space or get_space(None)
        self.room_type = room_type

    async def search(self, categories: list[str]) -> list[GroundingResult]:
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("PERPLEXITY_API_KEY", "Search Grounding")
            )

        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
        async with httpx.AsyncClient(timeout=90.0) as client:

            async def bounded(cat: str) -> GroundingResult:
                async with semaphore:
                    return await self._search_one(client, api_key, cat)

            return list(await asyncio.gather(*(bounded(cat) for cat in categories)))

    async def _search_one(
        self, client: httpx.AsyncClient, api_key: str, category: str
    ) -> GroundingResult:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = build_payload(category, self.model, space=self.space, room_type=self.room_type)
        allowed = approved_domains(self.space.retailers)

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            response = await client.post(PERPLEXITY_AGENT_URL, headers=headers, json=payload)
            if response.status_code < 400:
                return _parse_response(category, response.json(), allowed_domains=allowed)

            if response.status_code in _RETRYABLE_STATUSES and attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(_retry_delay(response, attempt))
                continue

            raise SearchGroundingError(
                response.status_code, self.model, _vendor_message(response)
            )

        raise SearchGroundingError(599, self.model, "retries exhausted")  # pragma: no cover


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return max(0.5, float(retry_after))
        except ValueError:
            pass
    return _RETRY_BASE_SECONDS * (2 ** (attempt - 1))


def _vendor_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:300] if text else response.reason_phrase or "no details"
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        message = error.get("message") or error.get("type") or error.get("code")
        if message:
            return str(message)
    if isinstance(error, str) and error.strip():
        return error.strip()
    detail = body.get("detail") if isinstance(body, dict) else None
    if detail:
        return str(detail)
    return response.reason_phrase or "no details"


def build_payload(
    category: str,
    model: str = _DEFAULT_MODEL,
    space: SpaceConfig | None = None,
    room_type: str | None = None,
) -> dict:
    space = space or get_space(None)
    return {
        "model": model,
        "instructions": space.search_instructions,
        "input": _build_query(category, space, room_type),
        # Required for anthropic/* models on the Agent API; harmless elsewhere.
        "max_output_tokens": _MAX_OUTPUT_TOKENS,
        "tools": [
            {
                "type": "web_search",
                "max_results": _MAX_RESULTS,
                "filters": {
                    "search_domain_filter": space.retailer_domains()[:_MAX_DOMAIN_FILTER]
                },
            }
        ],
    }


def _build_query(
    category: str, space: SpaceConfig | None = None, room_type: str | None = None
) -> str:
    return (space or get_space(None)).search_query(category, room_type)


def _parse_response(
    category: str, data: dict, allowed_domains: set[str] | None = None
) -> GroundingResult:
    allowed = allowed_domains if allowed_domains is not None else _APPROVED_RETAILER_DOMAINS
    urls: list[str] = []
    text_parts: list[str] = []

    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "search_results":
            for result in item.get("results", []) or []:
                url = result.get("url") if isinstance(result, dict) else None
                if isinstance(url, str) and _is_approved_retailer_url(url, allowed):
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
                    if isinstance(url, str) and _is_approved_retailer_url(url, allowed):
                        urls.append(url.strip())

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique_urls = [u for u in urls if not (u in seen or seen.add(u))]

    # Only include the text snippet when there are citation URLs to back it up.
    # A snippet without citations is ungrounded and not useful for Build Sheet generation.
    snippets = ["\n".join(text_parts)] if unique_urls and text_parts else []

    return {"category": category, "urls": unique_urls, "snippets": snippets}


def _is_approved_retailer_url(url: str, allowed_domains: set[str] | None = None) -> bool:
    host = urlparse(url.strip()).hostname
    if not host:
        return False

    allowed = allowed_domains if allowed_domains is not None else _APPROVED_RETAILER_DOMAINS
    normalized_host = host.removeprefix("www.").lower()
    return normalized_host in allowed
