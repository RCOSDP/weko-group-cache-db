#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Logger module for weko-group-cache-db."""

import logging
import traceback
import typing as t

from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text
from rich.traceback import install
from werkzeug.local import LocalProxy

from .config import config

if t.TYPE_CHECKING:
    from datetime import datetime


def _log_time_format(datetime: datetime) -> Text:
    """Format log time as ISO 8601 with milliseconds.

    Args:
        datetime (datetime): The datetime object to format.

    Returns:
        str: Formatted datetime string.

    """
    return Text(datetime.isoformat(timespec="milliseconds"))


console = Console(
    record=True,
    log_time_format=_log_time_format,
)


def setup_logger(name: str = __name__) -> logging.Logger:
    """Create and return a logger with the specified name.

    Args:
        name (str): The name of the logger.

    Returns:
        logging.Logger: Configured logger instance.

    """
    logger = logging.getLogger(name)
    logger.setLevel(config.LOG_LEVEL)

    handler = RichHandler(
        level=config.LOG_LEVEL,
        omit_repeated_times=False,
        rich_tracebacks=True,
        console=console,
        log_time_format=_log_time_format,
    )
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if config.DEVELOPMENT:
        install(console=console, extra_lines=2)
        traceback.print_exc = lambda: console.print_exception(extra_lines=2)

    return logger


logger = t.cast(logging.Logger, LocalProxy(lambda: logging.getLogger(__package__)))
