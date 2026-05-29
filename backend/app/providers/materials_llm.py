import importlib
from enum import Enum


class MaterialsLLM(Enum):
    """
    Enum of available Materials LLM providers.

    Each member encodes (slug, module_path, class_name) so that adding a fourth
    provider requires exactly one new adapter file plus one new enum entry here —
    no other files need editing.
    """

    ClaudeSonnet = (
        "claude_sonnet",
        "app.providers.claude_sonnet",
        "ClaudeSonnetAdapter",
    )
    Gpt5 = (
        "gpt5",
        "app.providers.gpt5",
        "Gpt5Adapter",
    )
    GeminiPro = (
        "gemini_pro",
        "app.providers.gemini_pro",
        "GeminiProAdapter",
    )

    def __new__(cls, slug: str, module_path: str, class_name: str) -> "MaterialsLLM":
        obj = object.__new__(cls)
        obj._value_ = slug
        obj._module_path = module_path
        obj._class_name = class_name
        return obj

    def make_adapter(self):
        """Instantiate and return the adapter for this Materials LLM."""
        module = importlib.import_module(self._module_path)
        adapter_class = getattr(module, self._class_name)
        return adapter_class()
