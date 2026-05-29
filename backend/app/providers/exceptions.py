class ImageProviderQuotaError(Exception):
    """Raised when an image provider reports an exhausted quota."""


class ImageProviderAuthError(Exception):
    """Raised when an image provider rejects credentials or authorization."""
