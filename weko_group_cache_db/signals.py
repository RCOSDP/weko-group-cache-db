#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Signal definitions for weko-group-cache-db."""

import typing as t

from datetime import datetime  # ruff: ignore[typing-only-standard-library-import]

from blinker import Namespace
from pydantic import BaseModel

namespace = Namespace()

# Define a custom signal for updating count
progress_signal = namespace.signal("progress")

# Define a custom signal for updating result
executed_signal = namespace.signal("executed")


class ProgressData(BaseModel):
    """Data model for progress signal."""

    status: t.Literal["started", "in_progress", "completed"]
    """Status of the fetch and cache operation."""

    total: int
    """Total number of institutions to process."""

    done: int
    """Number of institutions processed so far."""

    current: str
    """FQDN of the current institution being processed."""


class ExecutedData(BaseModel):
    """Data model for executed signal."""

    fqdn: str
    """FQDN of the institution."""

    status: t.Literal["success", "failed"]
    """Status of the fetch and cache operation."""

    retries: int = 0
    """Number of retries attempted."""

    error_type: str | None = None
    """Type of error, if any."""

    error_message: str | None = None
    """Error message, if any."""

    updated_at: datetime
    """Timestamp of the last update."""
