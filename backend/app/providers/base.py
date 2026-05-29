from abc import ABC, abstractmethod


class MissingApiKeyError(Exception):
    """Raised when a required API key environment variable is absent."""


def missing_api_key_message(env_var: str, feature: str) -> str:
    return (
        f"{env_var} is not set in the environment. "
        f"Set it in the environment, backend/.env.local, or secrets/{env_var} "
        f"to use {feature}."
    )


class ProviderAdapter(ABC):
    """Contract every Image Provider adapter must satisfy."""

    @abstractmethod
    async def generate(self, image_b64: str, prompt: str) -> list[bytes]:
        """
        Generate exactly 3 image variations.

        Args:
            image_b64: Base64-encoded source image bytes (the Site Photo or prior Render).
            prompt: The Composed Prompt describing the desired design changes.

        Returns:
            List of exactly 3 raw image bytes objects.

        Raises:
            MissingApiKeyError: If the required API key env var is not set.
        """


class MaterialsAdapter(ABC):
    """Contract every Materials LLM adapter must satisfy."""

    @abstractmethod
    async def generate_build_sheet(
        self,
        render_image_bytes: bytes,
        dimensions: dict,
        quality_tier: str,
        search_results: list[dict],
        feature_categories: list[str],
    ) -> dict:
        """
        Generate a structured Build Sheet from a Chosen Render and project context.

        Args:
            render_image_bytes: Raw bytes of the Chosen Render image.
            dimensions: Project Dimensions dict (e.g. {"deck_width_ft": 12, "deck_length_ft": 16}).
            quality_tier: One of "Budget", "Mid-range", or "Premium".
            search_results: Perplexity Search Grounding results, each a dict with
                            at minimum {"url": str, "snippet": str, "title": str}.
            feature_categories: List of Feature Category strings (e.g. ["Deck", "Garden Beds"]).

        Returns:
            Dict with keys: material_items (list), tool_list (list), build_steps (list),
            total_cost_range (str), skill_level (str), assumptions (list).

        Raises:
            MissingApiKeyError: If the required API key env var is not set.
        """
