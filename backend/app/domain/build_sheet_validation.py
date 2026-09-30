from __future__ import annotations

from copy import deepcopy
from urllib.parse import quote, quote_plus, urlparse

from app.domain.retailers import APPROVED_RETAILERS

_APPROVED_DOMAINS = {retailer["domain"] for retailer in APPROVED_RETAILERS}

# ---------------------------------------------------------------------------
# Working product links
# ---------------------------------------------------------------------------
# LLM-generated product-detail URLs are unreliable: they frequently 404, point
# at category/search pages, or get blocked by retailer bot protection. Rather
# than validate-and-drop them (which leaves the build sheet empty), we point
# every material at the retailer's SEARCH results for that item name. Those
# links always resolve in a browser and land the user on relevant products.
# The prompts therefore tell the model to leave product_url empty.

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
