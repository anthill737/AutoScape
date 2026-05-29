import importlib
from enum import Enum


class ImageProvider(Enum):
    """
    Enum of available Image Providers.

    Each member encodes (slug, module_path, class_name) so that adding a third
    provider requires exactly one new adapter file plus one new enum entry here —
    no other files need editing.
    """

    GeminiFlashImage = (
        "gemini_flash_image",
        "app.providers.gemini_flash",
        "GeminiFlashImageAdapter",
    )
    GptImage = ("gpt_image", "app.providers.gpt_image", "GptImageAdapter")

    def __new__(cls, slug: str, module_path: str, class_name: str) -> "ImageProvider":
        obj = object.__new__(cls)
        obj._value_ = slug
        obj._module_path = module_path
        obj._class_name = class_name
        return obj

    def make_adapter(self):
        """Instantiate and return the adapter for this provider."""
        module = importlib.import_module(self._module_path)
        adapter_class = getattr(module, self._class_name)
        return adapter_class()
