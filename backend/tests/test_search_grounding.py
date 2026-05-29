"""
Tests for SearchGrounding adapter.

Live Perplexity calls are skipped when PERPLEXITY_API_KEY is absent.
Parsing logic is tested against a recorded response shape using AsyncMock.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.retailers import APPROVED_RETAILERS
from app.providers.base import MissingApiKeyError
from app.providers.search_grounding import SearchGrounding, _build_query, _parse_response

_HOME_DEPOT = APPROVED_RETAILERS[0]
_LOWES = APPROVED_RETAILERS[1]

# ---------------------------------------------------------------------------
# _parse_response unit tests — no HTTP involved
# ---------------------------------------------------------------------------

_SAMPLE_RESPONSE = {
    "id": "cmpl-abc123",
    "model": "sonar",
    "citations": [
        f"https://www.{_HOME_DEPOT['domain']}/p/deck-boards/123",
        f"https://www.{_LOWES['domain']}/p/composite-decking/456",
        "https://www.trex.com/products/decking/",
    ],
    "choices": [
        {
            "index": 0,
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": (
                    "For deck projects, Trex composite decking (~$4–6/linear ft) is a top pick. "
                    f"{_HOME_DEPOT['name']} carries 16ft boards at around $48 each. "
                    "Pressure-treated 2x6 lumber averages $12–18 per 8ft board "
                    f"at {_LOWES['name']}."
                ),
            },
        }
    ],
    "usage": {"prompt_tokens": 50, "completion_tokens": 80, "total_tokens": 130},
}

_EMPTY_CITATIONS_RESPONSE = {
    "id": "cmpl-xyz",
    "model": "sonar",
    "citations": [],
    "choices": [
        {
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "No specific products found."},
        }
    ],
}

_NO_CONTENT_RESPONSE = {
    "id": "cmpl-xyz",
    "model": "sonar",
    "citations": ["https://example.com/product"],
    "choices": [],
}


def test_parse_response_extracts_urls_and_snippet():
    result = _parse_response("deck", _SAMPLE_RESPONSE)
    assert result["category"] == "deck"
    assert result["urls"] == [
        f"https://www.{_HOME_DEPOT['domain']}/p/deck-boards/123",
        f"https://www.{_LOWES['domain']}/p/composite-decking/456",
    ]
    assert len(result["snippets"]) == 1
    assert "Trex" in result["snippets"][0]


def test_parse_response_empty_citations_yields_empty_lists():
    result = _parse_response("garden beds", _EMPTY_CITATIONS_RESPONSE)
    assert result["category"] == "garden beds"
    assert result["urls"] == []
    assert result["snippets"] == []


def test_parse_response_no_choices_yields_empty_snippets():
    result = _parse_response("patio", _NO_CONTENT_RESPONSE)
    assert result["category"] == "patio"
    assert result["urls"] == []
    assert result["snippets"] == []


def test_parse_response_filters_blank_urls():
    data = {
        "citations": [f"https://{_HOME_DEPOT['domain']}/p/123", "", "  "],
        "choices": [],
    }
    result = _parse_response("fire feature", data)
    assert result["urls"] == [f"https://{_HOME_DEPOT['domain']}/p/123"]


def test_parse_response_missing_fields_does_not_crash():
    result = _parse_response("pergola", {})
    assert result["category"] == "pergola"
    assert result["urls"] == []
    assert result["snippets"] == []


def test_build_query_includes_approved_retailer_site_filters():
    query = _build_query("deck")

    assert "site:homedepot.com" in query
    assert "site:lowes.com" in query
    assert "site:menards.com" in query
    assert "site:acehardware.com" in query
    assert "site:costco.com" in query


def test_parse_response_discards_non_allowlisted_citations():
    data = {
        "citations": [
            f"https://www.{_HOME_DEPOT['domain']}/p/deck-boards/123",
            "https://www.amazon.com/dp/example",
        ],
        "choices": [
            {
                "message": {
                    "content": "Home Depot carries suitable deck boards."
                }
            }
        ],
    }

    result = _parse_response("deck", data)

    assert result["urls"] == [f"https://www.{_HOME_DEPOT['domain']}/p/deck-boards/123"]
    assert result["snippets"] == ["Home Depot carries suitable deck boards."]


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


def _make_mock_response(data: dict) -> MagicMock:
    """Build a mock httpx.Response that returns `data` from .json()."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@pytest.mark.asyncio
async def test_search_returns_one_result_per_category(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")

    mock_post = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

    with patch("app.providers.search_grounding.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = mock_post
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        grounding = SearchGrounding()
        results = await grounding.search(["deck", "garden beds"])

    assert len(results) == 2
    assert results[0]["category"] == "deck"
    assert results[1]["category"] == "garden beds"
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_search_sends_bearer_auth_header(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "secret-perplexity-key")

    captured_kwargs: list[dict] = []

    async def fake_post(url, **kwargs):
        captured_kwargs.append(kwargs)
        return _make_mock_response(_SAMPLE_RESPONSE)

    with patch("app.providers.search_grounding.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=fake_post)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        await SearchGrounding().search(["deck"])

    assert captured_kwargs, "post was never called"
    headers = captured_kwargs[0]["headers"]
    assert headers["Authorization"] == "Bearer secret-perplexity-key"


@pytest.mark.asyncio
async def test_search_result_urls_are_non_empty_strings(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")

    mock_post = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

    with patch("app.providers.search_grounding.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = mock_post
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await SearchGrounding().search(["deck"])

    result = results[0]
    assert all(isinstance(u, str) and u.strip() for u in result["urls"])


@pytest.mark.asyncio
async def test_search_zero_citations_returns_empty_lists_not_crash(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")

    mock_post = AsyncMock(return_value=_make_mock_response(_EMPTY_CITATIONS_RESPONSE))

    with patch("app.providers.search_grounding.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = mock_post
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await SearchGrounding().search(["fire feature"])

    assert results[0]["urls"] == []
    assert results[0]["snippets"] == []


# ---------------------------------------------------------------------------
# Live test (skipped without real key)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="requires live PERPLEXITY_API_KEY")
@pytest.mark.asyncio
async def test_live_search_returns_results():
    if not os.environ.get("PERPLEXITY_API_KEY"):
        pytest.skip("PERPLEXITY_API_KEY not set")

    grounding = SearchGrounding()
    results = await grounding.search(["deck lumber", "composite decking"])

    assert len(results) == 2
    for r in results:
        assert r["category"] in ("deck lumber", "composite decking")
        assert isinstance(r["urls"], list)
        assert isinstance(r["snippets"], list)
