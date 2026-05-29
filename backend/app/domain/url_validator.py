from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:x[a-z0-9]+)?", re.IGNORECASE)
_SEARCH_CATEGORY_SEGMENTS = {"b", "c", "category", "s", "search"}


def validate_material_item_url(item_name: str, candidate_url: str) -> tuple[bool, str]:
    """Validate that a material item URL resolves to a matching product page."""

    parsed_url = urlparse(candidate_url)
    if _is_search_or_category_path(parsed_url.path):
        return False, "URL appears to be a search/category page."

    try:
        response = httpx.get(candidate_url, timeout=5.0, follow_redirects=True)
    except httpx.TimeoutException:
        return False, "Request timed out while validating URL."
    except httpx.HTTPError as exc:
        return False, f"Request failed while validating URL: {exc}"

    if response.status_code != 200:
        return False, f"URL returned HTTP status {response.status_code}."

    title = _extract_title(response.text)
    item_tokens = _significant_tokens(item_name)
    title_tokens = _significant_tokens(title)
    if not item_tokens or item_tokens.isdisjoint(title_tokens):
        return False, "Title mismatch: page title has no significant token overlap with item name."

    return True, "URL passed validation."


def _is_search_or_category_path(path: str) -> bool:
    segments = [segment.lower() for segment in path.split("/") if segment]
    return any(segment in _SEARCH_CATEGORY_SEGMENTS for segment in segments)


def _extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title is None:
        return ""
    return soup.title.get_text(" ", strip=True)


def _significant_tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(value)
        if token.lower() not in _STOPWORDS
    }
