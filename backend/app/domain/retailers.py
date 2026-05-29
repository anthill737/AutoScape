APPROVED_RETAILERS = [
    {"name": "The Home Depot", "domain": "homedepot.com"},
    {"name": "Lowe's", "domain": "lowes.com"},
    {"name": "Menards", "domain": "menards.com"},
    {"name": "Ace Hardware", "domain": "acehardware.com"},
    {"name": "Costco", "domain": "costco.com"},
]

_APPROVED_RETAILER_LIST = ", ".join(
    f"{retailer['name']} ({retailer['domain']})" for retailer in APPROVED_RETAILERS
)

APPROVED_RETAILER_PROMPT_CONSTRAINT = (
    "Use only these approved retailers for material vendors and product URLs: "
    f"{_APPROVED_RETAILER_LIST}. Do not include Amazon, Wayfair, Walmart, "
    "marketplaces, wholesalers, manufacturer-only pages, or other unapproved retailers. "
    "When a real product URL is available, it must be from one of the approved retailer domains."
)

