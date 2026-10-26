#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Exceptions module for weko-group-cache-db."""


class WekoGroupCacheDbError(Exception):
    """Base exception class for weko-group-cache-db."""


class UpdateError(WekoGroupCacheDbError):
    """Exception class for update errors in weko-group-cache-db."""

    def __init__(self, fqdn: str, origin: Exception | None = None) -> None:
        """Initialize the exception with an optional original exception.

        Args:
            fqdn (str): The FQDN related to the error.
            origin (Exception | None): The original exception, if any.

        """
        super().__init__(fqdn)
        self.fqdn = fqdn
        self.origin = origin

    def __str__(self) -> str:  # ruff: ignore[undocumented-magic-method]
        return f"FQDN: {self.fqdn}, {self.origin}"


class ConfigurationError(WekoGroupCacheDbError):
    """Exception class for configuration errors in weko-group-cache-db."""
