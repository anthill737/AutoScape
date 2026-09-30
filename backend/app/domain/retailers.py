"""Approved retailers and the prompt constraint that keeps vendors on the allowlist.

``APPROVED_RETAILERS`` is the exterior (landscape) list and is kept for backward
compatibility; interior projects use the retailer list on their ``SpaceConfig``
(see ``app.domain.spaces``). The helpers below build the same prompt text and domain
set for any retailer list.
"""

from __future__ import annotations

APPROVED_RETAILERS = [
    {"name": "The Home Depot", "domain": "homedepot.com"},
    {"name": "Lowe's", "domain": "lowes.com"},
    {"name": "Menards", "domain": "menards.com"},
    {"name": "Ace Hardware", "domain": "acehardware.com"},
    {"name": "Costco", "domain": "costco.com"},
]

# Named in the prompt as explicitly off-limits unless a space approves them.
_COMMONLY_UNAPPROVED = ("Amazon", "Wayfair", "Walmart")


def approved_domains(retailers: list[dict]) -> set[str]:
    """Bare hostnames (no ``www.``) of the given retailers."""
    return {
        str(retailer["domain"]).removeprefix("www.").lower()
        for retailer in retailers
        if retailer.get("domain")
    }


def retailer_prompt_constraint(retailers: list[dict]) -> str:
    """Prompt sentence restricting material vendors to ``retailers``."""
    approved_names = {str(retailer["name"]).lower() for retailer in retailers}
    listing = ", ".join(f"{retailer['name']} ({retailer['domain']})" for retailer in retailers)
    banned = ", ".join(
        name for name in _COMMONLY_UNAPPROVED if name.lower() not in approved_names
    )
    return (
        "Use only these approved retailers as material vendors: "
        f"{listing}. Do not include {banned}, "
        "marketplaces, wholesalers, manufacturer-only pages, or other unapproved retailers. "
        "Do not invent product URLs; links are generated automatically."
    )


APPROVED_RETAILER_PROMPT_CONSTRAINT = retailer_prompt_constraint(APPROVED_RETAILERS)
