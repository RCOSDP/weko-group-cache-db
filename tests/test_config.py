#
# Copyright (C) 2025 National Institute of Informatics.
#
import typing as t

import toml

from werkzeug.local import LocalProxy

from weko_group_cache_db.config import Settings, _current_config, config, setup_config


def test_settings_default_values():
    default_cache_ttl = 86400
    default_request_timeout = 20
    default_request_interval = 3
    default_request_retries = 3
    default_request_retry_base = 4
    default_request_retry_factor = 5
    default_request_retry_max = 90

    settings = Settings(MAP_GROUPS_API_ENDPOINT="https://example.com/api/groups/")
    assert settings.DEVELOPMENT is False
    assert settings.LOG_LEVEL == "INFO"
    assert settings.SP_CONNECTOR_ID_PREFIX == "jc_"
    assert settings.CACHE_KEY_SUFFIX == "_gakunin_groups"
    assert settings.CACHE_TTL == default_cache_ttl
    assert settings.MAP_GROUPS_API_ENDPOINT == "https://example.com/api/groups/"
    assert settings.REQUEST_TIMEOUT == default_request_timeout
    assert settings.REQUEST_INTERVAL == default_request_interval
    assert settings.REQUEST_RETRIES == default_request_retries
    assert settings.REQUEST_RETRY_BASE == default_request_retry_base
    assert settings.REQUEST_RETRY_FACTOR == default_request_retry_factor
    assert settings.REQUEST_RETRY_MAX == default_request_retry_max
    assert settings.REDIS_URL == "redis://localhost:6379/4"


def test_setup_config(tmp_path, row_config):
    config_path = tmp_path / "config.toml"
    row_config = {key: value for key, value in row_config.items() if key == "MAP_GROUPS_API_ENDPOINT"}
    with config_path.open("w") as f:
        toml.dump(row_config, f)

    setup_config(str(config_path))
    assert t.cast(LocalProxy, config)._get_current_object() is _current_config.get()


def test_setup_config_overrides(tmp_path, row_config):
    config_path = tmp_path / "config.toml"
    with config_path.open("w") as f:
        toml.dump(row_config, f)

    config_ = Settings(toml_path=str(config_path))  # pyright: ignore[reportCallIssue]
    config_dict = config_.model_dump()

    row_config["REDIS_URL"] = "redis://redis:26379/2"
    row_config["REDIS_SENTINELS"] = [
        (sentinel["host"], str(sentinel["port"])) for sentinel in row_config.get("SENTINELS", [])
    ]

    assert config_dict == row_config


def test_setup_config_overrides_lower_case(tmp_path, row_config):
    config_path = tmp_path / "config.toml"
    lower_case_config = {key.lower(): value for key, value in row_config.items()}
    with config_path.open("w") as f:
        toml.dump(lower_case_config, f)

    config_ = Settings(toml_path=config_path)  # pyright: ignore[reportCallIssue]
    config_dict = config_.model_dump()

    row_config["REDIS_URL"] = "redis://redis:26379/2"
    row_config["REDIS_SENTINELS"] = [
        (sentinel["host"], str(sentinel["port"])) for sentinel in row_config.get("SENTINELS", [])
    ]

    assert config_dict == row_config


def test_setup_config_dict(row_config):
    setup_config(row_config)
    assert t.cast(LocalProxy, config)._get_current_object() is _current_config.get()


def test_setup_config_instance(row_config):
    setup_config(Settings(**row_config))
    assert t.cast(LocalProxy, config)._get_current_object() is _current_config.get()
