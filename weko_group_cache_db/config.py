#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Settings module for weko-group-cache-db."""

import typing as t

from contextvars import ContextVar
from pathlib import Path
from typing import overload

from pydantic import BaseModel, computed_field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from werkzeug.local import LocalProxy


class Settings(BaseSettings):
    """Settings for application with validation."""

    DEVELOPMENT: bool = False
    """Environment flag for development."""

    LOG_LEVEL: t.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    """Logging level.

    Possible values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
    """

    SP_CONNECTOR_ID_PREFIX: str = "jc_"
    """Prefix for SP connector ID."""

    CACHE_KEY_SUFFIX: str = "_gakunin_groups"
    """Cache key suffix of group information in Redis."""

    CACHE_TTL: t.Annotated[int, "seconds"] = 86400
    """Cache time-to-live of group information in Redis.

    If it specified less than 0, it will be considered as no expiration.
    """

    MAP_GROUPS_API_ENDPOINT: str = "https://sample.gakunin.jp/api/groups/"
    """Map groups API endpoint."""

    REQUEST_TIMEOUT: t.Annotated[int, "seconds"] = 20
    """Request timeout when connecting to mAP API."""

    REQUEST_INTERVAL: t.Annotated[int, "seconds"] = 3
    """Request interval when fetching groups from mAP API."""

    REQUEST_RETRIES: t.Annotated[int, "times"] = 3
    """Request retries when failed to fetch groups from mAP API."""

    REQUEST_RETRY_BASE: t.Annotated[int | float, "seconds"] = 4
    """Base time for exponential backoff during request retries."""

    REQUEST_RETRY_FACTOR: t.Annotated[int | float, "seconds"] = 5
    """Factor for exponential backoff during request retries."""

    REQUEST_RETRY_MAX: t.Annotated[int | float, "seconds"] = 90
    """Maximum time for exponential backoff during request retries."""

    REDIS_TYPE: t.Literal["RedisCache", "RedisSentinelCache"] = "RedisCache"
    """Redis type to use. `RedisCache` or `RedisSentinelCache` is allowed."""

    REDIS_HOST: str = "localhost"
    """Redis service host name."""

    REDIS_PORT: int = 6379
    """Redis service port number."""

    REDIS_DB_INDEX: int = 4
    """Redis DB index to use for caching group information."""

    @computed_field
    @property
    def REDIS_URL(self) -> str:  # ruff: ignore[invalid-function-name]
        """Redis URL for caching group information."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_INDEX}"

    REDIS_SENTINEL_MASTER: str | None = None
    """Server name of the Redis sentinel master."""

    SENTINELS: list[Sentinel] | None = None
    """A list of Redis sentinel configurations."""

    @computed_field
    @property
    def REDIS_SENTINELS(self) -> list[tuple[str, str]]:  # ruff: ignore[invalid-function-name]
        """A list of Redis sentinel host names and their ports."""
        return (
            [(sentinel.host, str(sentinel.port)) for sentinel in self.SENTINELS]
            if self.SENTINELS
            else []
        )

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        alias_generator=lambda s: s.lower(),
        validate_default=True,
        validate_by_name=True,
        validate_by_alias=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources.

        Returns:
            A tuple of customized settings sources sorted by priority.

        """
        toml_path: str | Path | None = init_settings().pop("toml_path", None)

        if toml_path is None:
            return super().settings_customise_sources(
                settings_cls,
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )

        if isinstance(toml_path, str):
            toml_path = Path(toml_path)
        toml_settings = TomlConfigSettingsSource(cls, toml_path)

        return (
            init_settings,
            toml_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


class Sentinel(BaseModel):
    """Redis sentinel configuration."""

    host: str
    """Sentinel host name."""

    port: int
    """Sentinel port number."""


_no_config_msg = "Config has not been initialized."
_current_config: ContextVar[Settings] = ContextVar("current_config")


@overload
def setup_config(config: dict[str, t.Any]) -> None: ...
@overload
def setup_config(config: str) -> None: ...
@overload
def setup_config(config: Settings) -> None: ...


def setup_config(config: dict[str, t.Any] | str | Settings) -> None:
    """Initialize the global config instance."""
    if isinstance(config, dict):
        _current_config.set(Settings(**config))  # pyright: ignore[reportCallIssue]
    elif isinstance(config, str):
        _current_config.set(Settings(toml_path=config))  # pyright: ignore[reportCallIssue]
    else:
        _current_config.set(config)


config = t.cast(Settings, LocalProxy(_current_config, unbound_message=_no_config_msg))
