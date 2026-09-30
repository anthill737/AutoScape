"""
Tests for SearchGrounding (Perplexity Agent API).

Live Perplexity calls are skipped when PERPLEXITY_API_KEY is absent.
Parsing logic is tested against the documented Agent API response shape.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.retailers import APPROVED_RETAILERS
from app.domain.spaces import get_space
from app.providers.base import MissingApiKeyError
from app.providers.search_grounding import (
    PERPLEXITY_AGENT_URL,
    SearchGrounding,
    SearchGroundingError,
    _parse_response,
    build_payload,
)

_HOME_DEPOT = APPROVED_RETAILERS[0]
_LOWES = APPROVED_RETAILERS[1]

# ---------------------------------------------------------------------------
# _parse_response unit tests — no HTTP involved
# ---------------------------------------------------------------------------


def _agent_response(results: list[dict], text: str | None, annotations: list[dict] | None = None):
    output = []
    if results is not None:
        output.append({"type": "search_results", "queries": ["deck materials"], "results": results})
    if text is not None:
        output.append(
            {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": text, "annotations": annotations or []}
                ],
            }
        )
    return {
        "id": "resp_abc123",
        "object": "response",
        "status": "completed",
        "model": "perplexity/sonar",
        "output": output,
        "usage": {"input_tokens": 50, "output_tokens": 80, "total_tokens": 130},
    }


_SAMPLE_RESPONSE = _agent_response(
    results=[
        {
            "id": 1,
            "url": f"https://www.{_HOME_DEPOT['domain']}/p/deck-boards/123",
            "title": "Deck boards",
            "snippet": "16ft boards",
        },
        {
            "id": 2,
            "url": f"https://www.{_LOWES['domain']}/p/composite-decking/456",
            "title": "Composite decking",
            "snippet": "Trex",
        },
        {"id": 3, "url": "https://www.trex.com/products/decking/", "title": "Trex", "snippet": ""},
    ],
    text=(
        "For deck projects, Trex composite decking (~$4-6/linear ft) is a top pick [2]. "
        f"{_HOME_DEPOT['name']} carries 16ft boards at around $48 each [1]."
    ),
)

_EMPTY_RESULTS_RESPONSE = _agent_response(results=[], text="No specific products found.")

_NO_MESSAGE_RESPONSE = _agent_response(
    results=[{"id": 1, "url": "https://example.com/product", "title": "x", "snippet": ""}],
    text=None,
)


def test_parse_response_extracts_urls_and_snippet():
    result = _parse_response("deck", _SAMPLE_RESPONSE)
    assert result["category"] == "deck"
    assert result["urls"] == [
        f"https://www.{_HOME_DEPOT['domain']}/p/deck-boards/123",
        f"https://www.{_LOWES['domain']}/p/composite-decking/456",
    ]
    assert len(result["snippets"]) == 1
    assert "Trex" in result["snippets"][0]


def test_parse_response_empty_results_yields_empty_lists():
    result = _parse_response("garden beds", _EMPTY_RESULTS_RESPONSE)
    assert result["category"] == "garden beds"
    assert result["urls"] == []
    assert result["snippets"] == []


def test_parse_response_no_message_yields_empty_snippets():
    result = _parse_response("patio", _NO_MESSAGE_RESPONSE)
    assert result["category"] == "patio"
    assert result["urls"] == []
    assert result["snippets"] == []


def test_parse_response_collects_url_citation_annotations_and_dedupes():
    url = f"https://{_HOME_DEPOT['domain']}/p/123"
    data = _agent_response(
        results=[{"id": 1, "url": url, "title": "x", "snippet": ""}],
        text="Home Depot has it [1].",
        annotations=[
            {"type": "url_citation", "url": url, "title": "x", "start_index": 0, "end_index": 5},
            {"type": "url_citation", "url": "https://www.amazon.com/dp/x", "title": "amazon"},
        ],
    )
    result = _parse_response("fire feature", data)
    assert result["urls"] == [url]


def test_parse_response_missing_fields_does_not_crash():
    result = _parse_response("pergola", {})
    assert result["category"] == "pergola"
    assert result["urls"] == []
    assert result["snippets"] == []


def test_parse_response_discards_non_allowlisted_results():
    data = _agent_response(
        results=[
            {"id": 1, "url": f"https://www.{_HOME_DEPOT['domain']}/p/deck-boards/123"},
            {"id": 2, "url": "https://www.amazon.com/dp/example"},
        ],
        text="Home Depot carries suitable deck boards.",
    )

    result = _parse_response("deck", data)

    assert result["urls"] == [f"https://www.{_HOME_DEPOT['domain']}/p/deck-boards/123"]
    assert result["snippets"] == ["Home Depot carries suitable deck boards."]


# ---------------------------------------------------------------------------
# Request payload
# ---------------------------------------------------------------------------


def test_build_payload_uses_web_search_tool_with_approved_domain_allowlist():
    payload = build_payload("deck")

    assert payload["model"] == "perplexity/sonar"
    assert "deck" in payload["input"]
    assert payload["max_output_tokens"] > 0
    tool = payload["tools"][0]
    assert tool["type"] == "web_search"
    assert set(tool["filters"]["search_domain_filter"]) == {
        r["domain"] for r in APPROVED_RETAILERS
    }
    # Sonar-era fields must be gone.
    assert "messages" not in payload
    assert "return_citations" not in payload


def test_build_payload_honors_model_override():
    payload = build_payload("deck", model="anthropic/claude-sonnet-4-6")
    assert payload["model"] == "anthropic/claude-sonnet-4-6"
    assert SearchGrounding(model="openai/gpt-5.6-luna").model == "openai/gpt-5.6-luna"


def test_build_payload_interior_uses_interior_domains_and_remodel_phrasing():
    interior = get_space("interior")
    payload = build_payload("Cabinets", space=interior, room_type="Kitchen")

    assert payload["input"].startswith(
        "List the best products and materials for a Cabinets kitchen remodel."
    )
    assert "landscaping" not in payload["input"]
    assert "landscaping" not in payload["instructions"]
    domains = payload["tools"][0]["filters"]["search_domain_filter"]
    assert domains == [
        "homedepot.com",
        "lowes.com",
        "ikea.com",
        "flooranddecor.com",
        "build.com",
        "wayfair.com",
    ]
    assert len(domains) <= 20

    # No room type falls back to a generic "room".
    assert "Cabinets room remodel" in build_payload("Cabinets", space=interior)["input"]
    # Default (no space) is the exterior behaviour.
    assert build_payload("deck") == build_payload("deck", space=get_space("exterior"))


def test_parse_response_filters_by_the_space_domains():
    ikea_url = "https://www.ikea.com/us/en/p/sektion-123/"
    data = _agent_response(
        results=[
            {"id": 1, "url": ikea_url},
            {"id": 2, "url": f"https://www.{_HOME_DEPOT['domain']}/p/1"},
            {"id": 3, "url": "https://www.menards.com/p/1"},
        ],
        text="IKEA and Home Depot carry these.",
    )
    interior_domains = set(get_space("interior").retailer_domains())

    interior = _parse_response("Cabinets", data, allowed_domains=interior_domains)
    assert interior["urls"] == [ikea_url, f"https://www.{_HOME_DEPOT['domain']}/p/1"]

    exterior = _parse_response("Cabinets", data)
    assert exterior["urls"] == [
        f"https://www.{_HOME_DEPOT['domain']}/p/1",
        "https://www.menards.com/p/1",
    ]


@pytest.mark.asyncio
async def test_search_uses_the_instance_space_and_room_type(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    captured: list[dict] = []

    async def fake_post(url, **kwargs):
        captured.append(kwargs["json"])
        return _make_mock_response(
            _agent_response(
                results=[{"id": 1, "url": "https://www.ikea.com/us/en/p/1/"}],
                text="IKEA has it [1].",
            )
        )

    ctx = _patched_client(AsyncMock(side_effect=fake_post))
    try:
        grounding = SearchGrounding(space=get_space("interior"), room_type="Bathroom")
        results = await grounding.search(["Plumbing Fixtures"])
    finally:
        ctx.stop()

    assert "Plumbing Fixtures bathroom remodel" in captured[0]["input"]
    assert "ikea.com" in captured[0]["tools"][0]["filters"]["search_domain_filter"]
    assert results[0]["urls"] == ["https://www.ikea.com/us/en/p/1/"]


# ---------------------------------------------------------------------------
# Missing API key test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    grounding = SearchGrounding()
    with pytest.raises(MissingApiKeyError, match="PERPLEXITY_API_KEY"):
        await grounding.search(["deck"])


# ---------------------------------------------------------------------------
# Mocked HTTP tests — verify request shape and response parsing end-to-end
# ---------------------------------------------------------------------------


def _make_mock_response(
    data: dict, status_code: int = 200, headers: dict | None = None
) -> MagicMock:
    """Build a mock httpx.Response that returns `data` from .json()."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.headers = headers or {}
    mock_resp.reason_phrase = "Too Many Requests" if status_code == 429 else "Error"
    mock_resp.text = ""
    mock_resp.json.return_value = data
    return mock_resp


def _patched_client(post):
    ctx = patch("app.providers.search_grounding.httpx.AsyncClient")
    MockClient = ctx.start()
    mock_client_instance = AsyncMock()
    mock_client_instance.post = post
    MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
    MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_search_returns_one_result_per_category(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    mock_post = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))
    ctx = _patched_client(mock_post)
    try:
        results = await SearchGrounding().search(["deck", "garden beds"])
    finally:
        ctx.stop()

    assert len(results) == 2
    assert results[0]["category"] == "deck"
    assert results[1]["category"] == "garden beds"
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_search_posts_to_agent_endpoint_with_bearer_auth(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "secret-perplexity-key")

    captured: list[tuple[str, dict]] = []

    async def fake_post(url, **kwargs):
        captured.append((url, kwargs))
        return _make_mock_response(_SAMPLE_RESPONSE)

    ctx = _patched_client(AsyncMock(side_effect=fake_post))
    try:
        await SearchGrounding(model="perplexity/sonar").search(["deck"])
    finally:
        ctx.stop()

    assert captured, "post was never called"
    url, kwargs = captured[0]
    assert url == PERPLEXITY_AGENT_URL == "https://api.perplexity.ai/v1/agent"
    assert kwargs["headers"]["Authorization"] == "Bearer secret-perplexity-key"
    assert kwargs["json"]["model"] == "perplexity/sonar"
    assert kwargs["json"]["tools"][0]["type"] == "web_search"


@pytest.mark.asyncio
async def test_search_result_urls_are_non_empty_strings(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    ctx = _patched_client(AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE)))
    try:
        results = await SearchGrounding().search(["deck"])
    finally:
        ctx.stop()

    result = results[0]
    assert result["urls"]
    assert all(isinstance(u, str) and u.strip() for u in result["urls"])


@pytest.mark.asyncio
async def test_search_zero_results_returns_empty_lists_not_crash(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    ctx = _patched_client(AsyncMock(return_value=_make_mock_response(_EMPTY_RESULTS_RESPONSE)))
    try:
        results = await SearchGrounding().search(["fire feature"])
    finally:
        ctx.stop()

    assert results[0]["urls"] == []
    assert results[0]["snippets"] == []


@pytest.mark.asyncio
async def test_search_retries_on_429_honoring_retry_after(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("app.providers.search_grounding.asyncio.sleep", fake_sleep)
    rate_limited = _make_mock_response(
        {"error": {"type": "rate_limit", "message": "slow down"}},
        status_code=429,
        headers={"retry-after": "2"},
    )
    mock_post = AsyncMock(side_effect=[rate_limited, _make_mock_response(_SAMPLE_RESPONSE)])
    ctx = _patched_client(mock_post)
    try:
        results = await SearchGrounding().search(["deck"])
    finally:
        ctx.stop()

    assert results[0]["urls"]
    assert mock_post.call_count == 2
    assert sleeps == [2.0]


@pytest.mark.asyncio
async def test_search_raises_vendor_message_after_retries_exhausted(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    monkeypatch.setattr("app.providers.search_grounding.asyncio.sleep", AsyncMock())
    rate_limited = _make_mock_response(
        {"error": {"type": "rate_limit", "message": "Rate limit exceeded for tier 0"}},
        status_code=429,
    )
    mock_post = AsyncMock(return_value=rate_limited)
    ctx = _patched_client(mock_post)
    try:
        with pytest.raises(SearchGroundingError) as exc_info:
            await SearchGrounding(model="perplexity/sonar").search(["deck"])
    finally:
        ctx.stop()

    assert exc_info.value.status_code == 429
    assert "HTTP 429" in str(exc_info.value)
    assert "Rate limit exceeded for tier 0" in str(exc_info.value)
    assert "perplexity/sonar" in str(exc_info.value)
    assert mock_post.call_count == 4


@pytest.mark.asyncio
async def test_search_does_not_retry_auth_errors(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "bad-key")
    unauthorized = _make_mock_response(
        {"error": "Invalid API key or out of credits"}, status_code=401
    )
    mock_post = AsyncMock(return_value=unauthorized)
    ctx = _patched_client(mock_post)
    try:
        with pytest.raises(SearchGroundingError, match="Invalid API key or out of credits"):
            await SearchGrounding().search(["deck"])
    finally:
        ctx.stop()
    assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_search_limits_concurrency(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    in_flight = 0
    peak = 0

    async def fake_post(url, **kwargs):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        return _make_mock_response(_SAMPLE_RESPONSE)

    ctx = _patched_client(AsyncMock(side_effect=fake_post))
    try:
        results = await SearchGrounding().search(["Deck", "Fire Feature", "Pool", "Patio"])
    finally:
        ctx.stop()

    assert len(results) == 4
    assert peak <= 2


# ---------------------------------------------------------------------------
# Live test (skipped without real key)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="requires live PERPLEXITY_API_KEY")
@pytest.mark.asyncio
async def test_live_search_returns_results():
    if not os.environ.get("PERPLEXITY_API_KEY"):
        pytest.skip("PERPLEXITY_API_KEY not set")

    grounding = SearchGrounding()
    results = await grounding.search(["deck"])
    assert results[0]["category"] == "deck"
