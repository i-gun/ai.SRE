"""Shared AzurePortal validation exception."""


class AzurePortalValidationError(ValueError):
    """Raised when an operation or target violates AzurePortal's bounded contract."""
