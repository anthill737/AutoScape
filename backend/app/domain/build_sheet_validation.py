from __future__ import annotations

import asyncio  # noqa: F401  (kept for test patch targets)
from copy import deepcopy
from urllib.parse import quote, quote_plus, urlparse

from app.domain.retailers import APPROVED_RETAILERS
from app.domain.url_validator import validate_material_item_url  # noqa: F401

_APPROVED_DOMAINS = {retailer["domain"] for retailer in APPROVED_RETAILERS}


def _is_approved_product_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False

    host = urlparse(value.strip()).hostname
    if not host:
        return False

    normalized_host = host.removeprefix("www.").lower()
    return normalized_host in _APPROVED_DOMAINS


def validate_build_sheet_approved_retailers(draft: dict) -> dict:
    """Remove material items whose product URLs are outside approved retailers."""

    result = deepcopy(draft)
    material_items = result.get("material_items", [])
    if not isinstance(material_items, list):
        result["material_items"] = []
        return result

    approved_items = [
        item
        for item in material_items
        if isinstance(item, dict) and _is_approved_product_url(item.get("product_url"))
    ]
    dropped_count = len(material_items) - len(approved_items)
    result["material_items"] = approved_items

    if dropped_count <= 0:
        result.pop("warning", None)
        return result

    assumptions = result.get("assumptions", [])
    if not isinstance(assumptions, list):
        assumptions = []
    item_word = "item" if dropped_count == 1 else "items"
    verb = "was" if dropped_count == 1 else "were"
    assumptions.append(
        f"{dropped_count} {item_word} from unapproved retailers {verb} omitted."
    )
    result["assumptions"] = assumptions

    if dropped_count > len(material_items) / 2:
        result["warning"] = (
            "More than half of the generated material items were omitted because "
            "they did not reference approved retailers."
        )
    else:
        result.pop("warning", None)

    return result


# ---------------------------------------------------------------------------
# Working product links
# ---------------------------------------------------------------------------
# LLM-generated product-detail URLs are unreliable: they frequently 404, point
# at category/search pages, or get blocked by retailer bot protection. Rather
# than validate-and-drop them (which leaves the build sheet empty), we point
# every material at the retailer's SEARCH results for that item name. Those
# links always resolve in a browser and land the user on relevant products.

_DEFAULT_DOMAIN = "homedepot.com"
_DOMAIN_DISPLAY = {retailer["domain"]: retailer["name"] for retailer in APPROVED_RETAILERS}


def _hd(query: str) -> str:
    # Home Depot uses a path-style search: /s/<term>
    return f"https://www.homedepot.com/s/{quote(query)}"


def _lowes(query: str) -> str:
    return f"https://www.lowes.com/search?searchTerm={quote_plus(query)}"


def _menards(query: str) -> str:
    return f"https://www.menards.com/main/search.html?search={quote_plus(query)}"


def _ace(query: str) -> str:
    return f"https://www.acehardware.com/search?query={quote_plus(query)}"


def _costco(query: str) -> str:
    return f"https://www.costco.com/CatalogSearch?keyword={quote_plus(query)}"


_SEARCH_BUILDERS = {
    "homedepot.com": _hd,
    "lowes.com": _lowes,
    "menards.com": _menards,
    "acehardware.com": _ace,
    "costco.com": _costco,
}


def _retailer_domain_for(item: dict) -> str:
    """Pick which approved retailer to search, honoring the model's intent."""
    # 1) If the model already used an approved retailer domain, keep it.
    url = item.get("product_url")
    if isinstance(url, str) and url.strip():
        host = (urlparse(url.strip()).hostname or "").removeprefix("www.").lower()
        if host in _APPROVED_DOMAINS:
            return host
    # 2) Otherwise map the model's vendor name to an approved retailer.
    vendor = item.get("vendor")
    if isinstance(vendor, str) and vendor.strip():
        v = vendor.strip().lower()
        for domain, name in _DOMAIN_DISPLAY.items():
            if domain.split(".")[0] in v or name.lower() in v:
                return domain
    # 3) Fall back to a sensible default.
    return _DEFAULT_DOMAIN


def _search_link(item: dict) -> str:
    name = item.get("name")
    query = (
        name.strip()
        if isinstance(name, str) and name.strip()
        else "landscaping materials"
    )
    domain = _retailer_domain_for(item)
    return _SEARCH_BUILDERS.get(domain, _hd)(query)


async def validate_build_sheet_material_urls(draft: dict) -> dict:
    """Give every material a working retailer search link. Never drops items.

    (Kept ``async`` because the API awaits it.)
    """
    result = deepcopy(draft)
    material_items = result.get("material_items", [])
    if not isinstance(material_items, list):
        result["material_items"] = []
        return result

    rebuilt: list[dict] = []
    for item in material_items:
        if not isinstance(item, dict):
            continue
        new_item = dict(item)
        new_item["product_url"] = _search_link(new_item)
        # Backfill a sensible vendor name when the model left it blank.
        if not (isinstance(new_item.get("vendor"), str) and new_item["vendor"].strip()):
            new_item["vendor"] = _DOMAIN_DISPLAY.get(_retailer_domain_for(new_item), "")
        rebuilt.append(new_item)

    result["material_items"] = rebuilt
    result.pop("warning", None)
    return result
