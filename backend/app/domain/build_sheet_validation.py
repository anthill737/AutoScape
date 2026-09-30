from __future__ import annotations

import re
from copy import deepcopy
from urllib.parse import quote, quote_plus, urlparse

from app.domain.retailers import APPROVED_RETAILERS, approved_domains

# ---------------------------------------------------------------------------
# Working product links
# ---------------------------------------------------------------------------
# LLM-generated product-detail URLs are unreliable: they frequently 404, point
# at category/search pages, or get blocked by retailer bot protection. Rather
# than validate-and-drop them (which leaves the build sheet empty), we point
# every material at the retailer's SEARCH results for that item name. Those
# links always resolve in a browser and land the user on relevant products.
# The prompts therefore tell the model to leave product_url empty.
#
# Which retailers are eligible depends on the project's space (see
# app.domain.spaces); the exterior list is the default for backward compatibility.

_DEFAULT_DOMAIN = "homedepot.com"
_FALLBACK_QUERY = "building materials"


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


def _ikea(query: str) -> str:
    return f"https://www.ikea.com/us/en/search/?q={quote_plus(query)}"


def _floor_and_decor(query: str) -> str:
    return f"https://www.flooranddecor.com/search?q={quote_plus(query)}"


def _build(query: str) -> str:
    return f"https://www.build.com/search?term={quote_plus(query)}"


def _wayfair(query: str) -> str:
    return f"https://www.wayfair.com/keyword.php?keyword={quote_plus(query)}"


# Keyed by bare retailer domain; every retailer in app.domain.spaces has an entry.
_SEARCH_BUILDERS = {
    "homedepot.com": _hd,
    "lowes.com": _lowes,
    "menards.com": _menards,
    "acehardware.com": _ace,
    "costco.com": _costco,
    "ikea.com": _ikea,
    "flooranddecor.com": _floor_and_decor,
    "build.com": _build,
    "wayfair.com": _wayfair,
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _retailer_domain_for(item: dict, retailers: list[dict]) -> str:
    """Pick which approved retailer to search, honoring the model's intent."""
    domains = approved_domains(retailers)
    # 1) If the model already used an approved retailer domain, keep it.
    url = item.get("product_url")
    if isinstance(url, str) and url.strip():
        host = (urlparse(url.strip()).hostname or "").removeprefix("www.").lower()
        if host in domains:
            return host
    # 2) Otherwise map the model's vendor name to an approved retailer. Matching ignores
    #    punctuation and spacing so "Home Depot", "Floor and Decor" and "IKEA" all resolve.
    vendor = item.get("vendor")
    if isinstance(vendor, str) and vendor.strip():
        v = _normalize(vendor)
        for retailer in retailers:
            domain = str(retailer["domain"]).removeprefix("www.").lower()
            domain_part = domain.split(".")[0]
            name = _normalize(str(retailer["name"]))
            if domain_part in v or name in v or v in name:
                return domain
    # 3) Fall back to a sensible default: Home Depot when approved, else the first retailer.
    if _DEFAULT_DOMAIN in domains or not retailers:
        return _DEFAULT_DOMAIN
    return str(retailers[0]["domain"]).removeprefix("www.").lower()


def _search_link(item: dict, retailers: list[dict]) -> str:
    name = item.get("name")
    query = name.strip() if isinstance(name, str) and name.strip() else _FALLBACK_QUERY
    domain = _retailer_domain_for(item, retailers)
    return _SEARCH_BUILDERS.get(domain, _hd)(query)


async def validate_build_sheet_material_urls(
    draft: dict, retailers: list[dict] | None = None
) -> dict:
    """Give every material a working retailer search link. Never drops items.

    ``retailers`` is the project's approved list (``SpaceConfig.retailers``); ``None``
    uses the exterior list. (Kept ``async`` because the API awaits it.)
    """
    retailers = [dict(r) for r in retailers] if retailers else [dict(r) for r in APPROVED_RETAILERS]
    display = {str(r["domain"]).removeprefix("www.").lower(): str(r["name"]) for r in retailers}

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
        new_item["product_url"] = _search_link(new_item, retailers)
        # Backfill a sensible vendor name when the model left it blank.
        if not (isinstance(new_item.get("vendor"), str) and new_item["vendor"].strip()):
            new_item["vendor"] = display.get(_retailer_domain_for(new_item, retailers), "")
        rebuilt.append(new_item)

    result["material_items"] = rebuilt
    result.pop("warning", None)
    return result
