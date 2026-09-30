import importlib
from enum import Enum


class ImageProvider(Enum):
    """
    Enum of available Image Providers.

    Each member encodes (slug, module_path, class_name). The slug is the stable value
    stored in the database and sent by the frontend; the concrete *model* within the
    vendor is chosen per request (see ``make_adapter(model=...)``) from the live model
    catalog in ``app.providers.model_catalog``.
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

    def make_adapter(self, model: str | None = None):
        """Instantiate and return the adapter for this provider (vendor default if None)."""
        module = importlib.import_module(self._module_path)
        adapter_class = getattr(module, self._class_name)
        return adapter_class(model=model)
