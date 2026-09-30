"""Curated quality / cost / status metadata for vendor models.

Vendors' list-models endpoints return ids only: no price, no quality, no "this one is
retired". This table layers that on so the UI can show a real comparison instead of a
list of ids. Prices are vendor list prices verified on 2026-09-30 (standard tier,
$ per 1M tokens unless stated). Anything not matched by a rule shows as "unknown"
rather than guessed. Quality is a relative 1-5 within the provider's role.

Rules are matched in order, first match wins, per provider slug. Dated snapshots
(``...-2026-09-08``) inherit the base model's metadata and are marked non-current.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace

_SNAPSHOT_RE = re.compile(r"^(?P<base>.+?)-(?P<date>\d{4}-\d{2}-\d{2})$")
_VERSION_AT_RE = re.compile(r"^(?P<base>.+?)@(?P<ver>[\w-]+)$")


@dataclass(frozen=True)
class ModelMeta:
    # best | balanced | fast | legacy | unknown
    tier: str = "unknown"
    # 1 (weakest) .. 5 (strongest) within its role, None when unknown.
    quality: int | None = None
    # Human-readable price, e.g. "~$0.07 / image" or "$4 in · $20 out per 1M tokens".
    cost: str | None = None
    # 1 (cheapest) .. 5 (priciest) within its role, None when unknown.
    cost_rank: int | None = None
    recommended: bool = False
    # Short caveat shown next to the model, e.g. "Retired 2026-06-25".
    note: str | None = None
    # False hides the model behind "show older / snapshot models" in the UI.
    current: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


UNKNOWN = ModelMeta()


def _tok(inp: float, out: float) -> str:
    def fmt(v: float) -> str:
        return f"${v:g}"

    return f"{fmt(inp)} in · {fmt(out)} out per 1M tokens"


# ---------------------------------------------------------------------------
# Per-provider rule tables: (regex on model id, metadata)
# ---------------------------------------------------------------------------

_OPENAI_IMAGE: list[tuple[str, ModelMeta]] = [
    (
        r"^gpt-image-2\.5-sunburst$",
        ModelMeta(
            tier="best",
            quality=5,
            cost="Token-billed: $8 image in · $30 image out per 1M; roughly a few cents per image",
            cost_rank=3,
            note="Most capable for edits; supports xhigh/max quality",
        ),
    ),
    (
        r"^gpt-image-2\.5-flare$",
        ModelMeta(
            tier="balanced",
            quality=4,
            cost="Token-billed: $8 image in · $30 image out per 1M; roughly a few cents per image",
            cost_rank=2,
            recommended=True,
            note="Fast everyday model; near-Sunburst quality at half the latency",
        ),
    ),
    (
        r"^gpt-image-2$",
        ModelMeta(
            tier="legacy",
            quality=3,
            cost="Token-billed: $8 image in · $30 image out per 1M",
            cost_rank=3,
            note="Previous generation; no shutdown announced",
        ),
    ),
    (
        r"^gpt-image-1\.5$",
        ModelMeta(
            tier="legacy",
            quality=3,
            cost="~$0.034 / image at medium 1024×1024",
            cost_rank=3,
            note="Shuts down 2026-12-01",
            current=False,
        ),
    ),
    (
        r"^gpt-image-1-mini$",
        ModelMeta(
            tier="fast",
            quality=2,
            cost="~$0.011 / image at medium 1024×1024",
            cost_rank=1,
            note="Shuts down 2026-12-01",
            current=False,
        ),
    ),
    (
        r"^gpt-image-1$",
        ModelMeta(
            tier="legacy",
            quality=2,
            cost="~$0.042 / image at medium 1024×1024",
            cost_rank=4,
            note="Two generations old; highest token rates",
            current=False,
        ),
    ),
    (
        r"^chatgpt-image-latest$",
        ModelMeta(tier="legacy", note="Floating alias; shuts down 2026-12-01", current=False),
    ),
]

_GOOGLE_IMAGE: list[tuple[str, ModelMeta]] = [
    (
        r"^gemini-3-pro-image-preview$",
        ModelMeta(tier="legacy", note="Shut down 2026-06-25; use gemini-3-pro-image", current=False),
    ),
    (
        r"^gemini-3\.1-flash-image-preview$",
        ModelMeta(tier="legacy", note="Preview retired; use gemini-3.1-flash-image", current=False),
    ),
    (
        r"^gemini-2\.5-flash-image(-preview)?$",
        ModelMeta(
            tier="legacy",
            quality=2,
            cost="$0.039 / image",
            cost_rank=2,
            note="Shuts down 2026-10-02",
            current=False,
        ),
    ),
    (
        r"^gemini-3-pro-image$",
        ModelMeta(
            tier="best",
            quality=5,
            cost="$0.134 / image at 1K–2K, $0.24 at 4K",
            cost_rank=5,
            note="Nano Banana Pro; best fidelity, slowest",
        ),
    ),
    (
        r"^gemini-3\.1-flash-image$",
        ModelMeta(
            tier="balanced",
            quality=4,
            cost="$0.067 / image at 1K ($0.045 at 0.5K, $0.15 at 4K)",
            cost_rank=3,
            recommended=True,
            note="Nano Banana 2; no free-tier quota",
        ),
    ),
    (
        r"^gemini-3\.1-flash-lite-image$",
        ModelMeta(
            tier="fast",
            quality=3,
            cost="$0.034 / image (1K only)",
            cost_rank=1,
            note="Nano Banana 2 Lite; cheapest, 1K output only",
        ),
    ),
]

_ANTHROPIC: list[tuple[str, ModelMeta]] = [
    (
        r"^claude-fable-5-1$",
        ModelMeta(
            tier="best",
            quality=5,
            cost=_tok(10, 50),
            cost_rank=5,
            note="Most capable; overkill for a build sheet",
        ),
    ),
    (r"^claude-fable-5$", ModelMeta(tier="best", quality=5, cost=_tok(10, 50), cost_rank=5)),
    (
        r"^claude-opus-5-5$",
        ModelMeta(
            tier="best",
            quality=5,
            cost=_tok(4, 20),
            cost_rank=3,
            recommended=True,
            note="Current Opus; cheaper than Opus 5",
        ),
    ),
    (r"^claude-opus-5$", ModelMeta(tier="best", quality=5, cost=_tok(5, 25), cost_rank=4)),
    (r"^claude-opus-4-[678]$", ModelMeta(tier="legacy", quality=4, cost=_tok(5, 25), cost_rank=4)),
    (
        r"^claude-opus-4-5$",
        ModelMeta(tier="legacy", quality=4, cost=_tok(5, 25), cost_rank=4, current=False),
    ),
    (
        r"^claude-sonnet-5-5$",
        ModelMeta(
            tier="balanced",
            quality=4,
            cost=_tok(2, 10),
            cost_rank=2,
            note="Current Sonnet; best value for structured output",
        ),
    ),
    (r"^claude-sonnet-5$", ModelMeta(tier="balanced", quality=4, cost=_tok(2, 10), cost_rank=2)),
    (r"^claude-sonnet-4-6$", ModelMeta(tier="legacy", quality=3, cost=_tok(3, 15), cost_rank=3)),
    (
        r"^claude-sonnet-4(-5)?(-\d{8})?$",
        ModelMeta(tier="legacy", quality=3, cost=_tok(3, 15), cost_rank=3, current=False),
    ),
    (
        r"^claude-haiku-4-5$",
        ModelMeta(
            tier="fast",
            quality=2,
            cost=_tok(1, 5),
            cost_rank=1,
            note="Cheapest; fine for simple sheets",
        ),
    ),
    (r"^claude-(3|haiku-3|opus-3|sonnet-3)", ModelMeta(tier="legacy", quality=1, current=False)),
]

_OPENAI_TEXT: list[tuple[str, ModelMeta]] = [
    (
        r"^gpt-6-astra$",
        ModelMeta(tier="best", quality=5, cost=_tok(10, 50), cost_rank=5, note="Most capable; pricey"),
    ),
    (
        r"^gpt-6\.1-sol$",
        ModelMeta(
            tier="best",
            quality=5,
            cost=_tok(2, 10),
            cost_rank=3,
            note="Near-Astra quality at a fifth of the price",
        ),
    ),
    (
        r"^gpt-6-sol$",
        ModelMeta(tier="best", quality=4, cost=_tok(2, 10), cost_rank=3, note="Superseded by gpt-6.1-sol"),
    ),
    (
        r"^gpt-6-luna$",
        ModelMeta(
            tier="fast",
            quality=3,
            cost=_tok(0.10, 0.50),
            cost_rank=1,
            note="Most efficient GPT-6; very cheap",
        ),
    ),
    (
        r"^gpt-5\.6-sol$",
        ModelMeta(tier="best", quality=4, cost=_tok(4, 20), cost_rank=4, note="GPT-5.6 flagship"),
    ),
    (
        r"^gpt-5\.6-terra$",
        ModelMeta(
            tier="balanced",
            quality=4,
            cost=_tok(2, 12),
            cost_rank=3,
            recommended=True,
            note="Balances intelligence and cost",
        ),
    ),
    (
        r"^gpt-5\.6-luna$",
        ModelMeta(tier="fast", quality=3, cost=_tok(0.20, 1.20), cost_rank=1, note="Cost-optimised"),
    ),
    (r"^gpt-5\.5$", ModelMeta(tier="balanced", quality=4, cost=_tok(5, 30), cost_rank=5)),
    (r"^gpt-5\.4$", ModelMeta(tier="legacy", quality=3, cost=_tok(2.5, 15), cost_rank=3)),
    (r"^gpt-5\.4-mini$", ModelMeta(tier="legacy", quality=2, cost=_tok(0.75, 4.5), cost_rank=2)),
    (r"^gpt-5\.4-nano$", ModelMeta(tier="legacy", quality=1, cost=_tok(0.20, 1.25), cost_rank=1)),
    (
        r"^gpt-5$",
        ModelMeta(tier="legacy", quality=3, cost=_tok(1.25, 10), cost_rank=3, note="Shuts down 2026-12-11", current=False),
    ),
    (
        r"^gpt-5-mini$",
        ModelMeta(tier="legacy", quality=2, cost=_tok(0.25, 2), cost_rank=2, note="Shuts down 2026-12-11", current=False),
    ),
    (
        r"^gpt-5-nano$",
        ModelMeta(tier="legacy", quality=1, cost=_tok(0.05, 0.40), cost_rank=1, note="Shuts down 2026-12-11", current=False),
    ),
]

_GOOGLE_TEXT: list[tuple[str, ModelMeta]] = [
    (
        r"^gemini-3\.8-flash$",
        ModelMeta(
            tier="balanced",
            quality=4,
            cost=_tok(0.75, 3.75) + " (promo until 2026-12-31); free tier",
            cost_rank=2,
            recommended=True,
            note="Most intelligent Flash; free tier available",
        ),
    ),
    (
        r"^gemini-3\.[67]-flash$",
        ModelMeta(tier="balanced", quality=4, cost=_tok(0.75, 3.75) + "; free tier", cost_rank=2),
    ),
    (
        r"^gemini-3\.5-flash$",
        ModelMeta(tier="legacy", quality=3, cost=_tok(1.5, 9) + "; free tier", cost_rank=3),
    ),
    (
        r"^gemini-3\.1-pro-preview",
        ModelMeta(
            tier="best",
            quality=5,
            cost=_tok(2, 12),
            cost_rank=4,
            note="Preview only; strongest Gemini reasoning; no free tier",
        ),
    ),
    (
        r"^gemini-3\.5-flash-lite$",
        ModelMeta(tier="fast", quality=3, cost=_tok(0.30, 2.5) + "; free tier", cost_rank=1, note="Cheapest current Gemini"),
    ),
    (
        r"^gemini-3\.1-flash-lite$",
        ModelMeta(tier="fast", quality=3, cost=_tok(0.25, 1.5) + "; free tier", cost_rank=1, note="Shuts down 2027-05-07"),
    ),
    (r"^gemini-3\.1-flash-lite-preview$", ModelMeta(tier="legacy", note="Shutdown announced", current=False)),
    (
        r"^gemini-3-flash-preview$",
        ModelMeta(tier="legacy", quality=3, cost=_tok(0.5, 3) + "; free tier", cost_rank=1, current=False),
    ),
    (
        r"^gemini-omni-flash-preview$",
        ModelMeta(tier="legacy", note="Deprecated 2026-09-30; video model", current=False),
    ),
    (
        r"^gemini-2\.5-pro$",
        ModelMeta(tier="legacy", quality=4, cost=_tok(1.25, 10) + "; free tier", cost_rank=3, note="Access limited to existing projects"),
    ),
    (
        r"^gemini-2\.5-flash$",
        ModelMeta(tier="legacy", quality=3, cost=_tok(0.30, 2.5) + "; free tier", cost_rank=1, note="Access limited to existing projects"),
    ),
    (
        r"^gemini-2\.5-flash-lite$",
        ModelMeta(tier="legacy", quality=2, cost=_tok(0.10, 0.40) + "; free tier", cost_rank=1, note="Access limited to existing projects"),
    ),
    (r"-latest$", ModelMeta(tier="unknown", note="Floating alias; resolves to a newer model", current=False)),
    (r"-customtools$", ModelMeta(tier="unknown", note="Tool-calling variant", current=False)),
]

_SEARCH_FEE = " + $0.0025 per web search"

_PERPLEXITY: list[tuple[str, ModelMeta]] = [
    (
        r"^perplexity/sonar$",
        ModelMeta(
            tier="balanced",
            quality=3,
            cost=_tok(0.25, 2.5) + _SEARCH_FEE,
            cost_rank=1,
            recommended=True,
            note="Perplexity's own search model; cheapest and tuned for citations",
        ),
    ),
    (r"^perplexity/", ModelMeta(tier="balanced", quality=3, note="Perplexity-hosted open model" + _SEARCH_FEE)),
    (
        r"^anthropic/claude-(fable|opus)",
        ModelMeta(tier="best", quality=5, cost_rank=5, note="Billed at Anthropic's rates" + _SEARCH_FEE),
    ),
    (
        r"^anthropic/claude-sonnet",
        ModelMeta(tier="balanced", quality=4, cost_rank=3, note="Billed at Anthropic's rates" + _SEARCH_FEE),
    ),
    (
        r"^anthropic/claude-haiku",
        ModelMeta(tier="fast", quality=2, cost_rank=2, note="Billed at Anthropic's rates" + _SEARCH_FEE),
    ),
    (
        r"^openai/gpt-6-astra",
        ModelMeta(tier="best", quality=5, cost=_tok(10, 50) + _SEARCH_FEE, cost_rank=5),
    ),
    (
        r"^openai/gpt-(6\.1-sol|6-sol)",
        ModelMeta(tier="best", quality=5, cost=_tok(2, 10) + _SEARCH_FEE, cost_rank=3),
    ),
    (r"^openai/gpt-6-luna", ModelMeta(tier="fast", quality=3, cost=_tok(0.10, 0.50) + _SEARCH_FEE, cost_rank=1)),
    (r"^openai/gpt-5\.6-luna", ModelMeta(tier="fast", quality=3, cost=_tok(0.20, 1.20) + _SEARCH_FEE, cost_rank=1)),
    (r"^openai/gpt-5\.6-terra", ModelMeta(tier="balanced", quality=4, cost=_tok(2, 12) + _SEARCH_FEE, cost_rank=3)),
    (r"^openai/", ModelMeta(tier="balanced", quality=4, cost_rank=4, note="Billed at OpenAI's rates" + _SEARCH_FEE)),
    (
        r"^google/gemini-3\.8-flash",
        ModelMeta(tier="balanced", quality=4, cost=_tok(0.75, 3.75) + _SEARCH_FEE, cost_rank=2),
    ),
    (r"^google/gemini.*pro", ModelMeta(tier="best", quality=5, cost_rank=4, note="Billed at Google's rates" + _SEARCH_FEE)),
    (r"^google/", ModelMeta(tier="balanced", quality=4, cost_rank=2, note="Billed at Google's rates" + _SEARCH_FEE)),
    (r"^(xai|zai|moonshot|nvidia)/", ModelMeta(tier="balanced", quality=3, note="Third-party model via Perplexity" + _SEARCH_FEE)),
]

_RULES_BY_SLUG: dict[str, list[tuple[re.Pattern[str], ModelMeta]]] = {
    slug: [(re.compile(pattern), meta) for pattern, meta in rules]
    for slug, rules in {
        "gpt_image": _OPENAI_IMAGE,
        "gemini_flash_image": _GOOGLE_IMAGE,
        "claude_sonnet": _ANTHROPIC,
        "gpt5": _OPENAI_TEXT,
        "gemini_pro": _GOOGLE_TEXT,
        "perplexity": _PERPLEXITY,
    }.items()
}


def _match(slug: str, model_id: str) -> ModelMeta | None:
    for pattern, meta in _RULES_BY_SLUG.get(slug, []):
        if pattern.search(model_id):
            return meta
    return None


def annotate(slug: str, model_id: str) -> ModelMeta:
    """Return curated metadata for ``model_id`` under provider ``slug``."""
    direct = _match(slug, model_id)
    if direct is not None:
        return direct

    snapshot = _SNAPSHOT_RE.match(model_id) or _VERSION_AT_RE.match(model_id)
    if snapshot:
        base = snapshot.group("base")
        base_meta = _match(slug, base) or UNKNOWN
        return replace(
            base_meta,
            recommended=False,
            current=False,
            note=f"Dated snapshot of {base}; same model, pinned version",
        )

    return UNKNOWN
