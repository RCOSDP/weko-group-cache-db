#
# Copyright (C) 2025 National Institute of Informatics.
#

import typing as t

from logging import INFO

import pytest

from click.testing import CliRunner

from weko_group_cache_db.config import Settings, _current_config


@pytest.fixture
def runner(monkeypatch):
    """Fixture for invoking command-line interfaces.

    Returns:
        CliRunner: A CliRunner instance.

    """
    monkeypatch.setenv("COLUMNS", "80")
    return CliRunner()


@pytest.fixture
def set_test_config():
    def _set_test_config(**kwargs: t.Any) -> Settings:
        kwargs.setdefault("MAP_GROUPS_API_ENDPOINT", "https://sample.gakunin.jp/api/groups/")
        test_config = Settings(**kwargs)
        _current_config.set(test_config)
        return test_config

    return _set_test_config


@pytest.fixture
def row_config():
    return {
        "DEVELOPMENT": True,
        "LOG_LEVEL": "WARNING",
        "SP_CONNECTOR_ID_PREFIX": "test_jc_",
        "CACHE_KEY_SUFFIX": "_test_gakunin_groups",
        "CACHE_TTL": 43200,
        "MAP_GROUPS_API_ENDPOINT": "https://sample.gakunin.jp/api/groups/",
        "REQUEST_TIMEOUT": 25,
        "REQUEST_INTERVAL": 10,
        "REQUEST_RETRIES": 5,
        "REQUEST_RETRY_BASE": 2,
        "REQUEST_RETRY_FACTOR": 15,
        "REQUEST_RETRY_MAX": 60,
        "REDIS_TYPE": "RedisSentinelCache",
        "REDIS_HOST": "redis",
        "REDIS_PORT": 26379,
        "REDIS_DB_INDEX": 2,
        "REDIS_SENTINEL_MASTER": "testmaster",
        "SENTINELS": [{"host": "redis1", "port": 26378}, {"host": "redis2", "port": 26377}],
    }


@pytest.fixture
def log_capture(caplog) -> pytest.LogCaptureFixture:
    caplog.set_level(INFO)
    return caplog


@pytest.fixture
def institutions_data():
    def _data(num: int) -> list[dict[str, str]]:
        return [
            {
                "name": f"institution_{i}",
                "fqdn": f"example{i}.ac.jp",
                "sp_connector_id": f"test_jc_example{i}_ac_jp",
                "client_cert_path": f"/path/to/client_cert_{i}.pem",
                "client_key_path": f"/path/to/client_key_{i}.pem",
            }
            for i in range(1, num + 1)
        ]

    return _data


@pytest.fixture
def institutions_data_alias(institutions_data):
    def _data(num: int) -> list[dict[str, str]]:
        data = institutions_data(num)
        return [
            {
                "name": inst["name"],
                "fqdn": inst["fqdn"],
                "spid": inst["sp_connector_id"],
                "cert": inst["client_cert_path"],
                "key": inst["client_key_path"],
            }
            for inst in data
        ]

    return _data
