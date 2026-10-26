#
# Copyright (C) 2025 National Institute of Informatics.
#


from unittest.mock import MagicMock, patch

import pytest
import redis
import redis.sentinel

from redis.exceptions import ConnectionError as RedisConnectionError

from weko_group_cache_db.redis import _redis_connection, _sentinel_connection, connection


# def connection() -> Redis:
def test_connection_redis(set_test_config, log_capture: pytest.LogCaptureFixture):
    set_test_config(REDIS_TYPE="RedisCache")
    with patch("weko_group_cache_db.redis._redis_connection") as mock_redis_connection:
        mock_redis_connection.return_value = MagicMock(spec=redis.Redis)
        store = connection()

    mock_redis_connection.assert_called_once()
    mock_redis_connection.return_value.ping.assert_called_once()
    assert store == mock_redis_connection.return_value
    assert log_capture.records[0].getMessage() == "Successfully connected to Redis."


def test_connection_sentinel(set_test_config, log_capture: pytest.LogCaptureFixture):
    set_test_config(REDIS_TYPE="RedisSentinelCache")
    with patch("weko_group_cache_db.redis._sentinel_connection") as mock_sentinel_connection:
        mock_sentinel_connection.return_value = MagicMock(spec=redis.Redis)
        store = connection()

    mock_sentinel_connection.assert_called_once()
    mock_sentinel_connection.return_value.ping.assert_called_once()
    assert store == mock_sentinel_connection.return_value
    assert log_capture.records[0].getMessage() == "Successfully connected to Redis Sentinel."


def test_connection_catch_value_error(set_test_config, log_capture: pytest.LogCaptureFixture):
    set_test_config(REDIS_TYPE="RedisCache")
    with patch("weko_group_cache_db.redis._redis_connection") as mock_redis_connection:
        mock_redis_connection.side_effect = ValueError("Test ValueError")
        with pytest.raises(ValueError, match="Test ValueError"):
            connection()

    assert log_capture.records[0].getMessage() == "Failed to connect to Redis. Invalid configuration."


def test_connection_catch_connection_error(set_test_config, log_capture: pytest.LogCaptureFixture):
    set_test_config(REDIS_TYPE="RedisCache")
    with patch("weko_group_cache_db.redis._redis_connection") as mock_redis_connection:
        mock_store = MagicMock(spec=redis.Redis)
        mock_store.ping.side_effect = RedisConnectionError("Test ConnectionError")
        mock_redis_connection.return_value = mock_store
        with pytest.raises(RedisConnectionError, match="Test ConnectionError"):
            connection()

    assert log_capture.records[0].getMessage() == "Failed to connect to Redis. Something went wrong on Redis."


# def _redis_connection() -> Redis:
def test__redis_connection(set_test_config):
    set_test_config(REDIS_HOST="localhost", REDIS_PORT=6379, REDIS_DB_INDEX=4)
    with patch("weko_group_cache_db.redis.Redis.from_url") as mock_redis_from_url:
        mock_redis_from_url.return_value = MagicMock(spec=redis.Redis)
        store = _redis_connection()

    mock_redis_from_url.assert_called_once_with("redis://localhost:6379/4")
    assert store == mock_redis_from_url.return_value


# def _sentinel_connection() -> Redis:
def test__sentinel_connection(set_test_config):
    set_test_config(
        SENTINELS=[{"host": "localhost", "port": 26379}, {"host": "localhost", "port": 26380}],
        REDIS_SENTINEL_MASTER="test_master",
        REDIS_DB_INDEX=4,
    )
    mock_sentinels = MagicMock(spec=redis.sentinel.Sentinel)
    with patch("weko_group_cache_db.redis.sentinel.Sentinel") as mock_redis_sentinel:
        mock_redis_sentinel.return_value = mock_sentinels
        store = _sentinel_connection()

    mock_redis_sentinel.assert_called_once_with(
        [("localhost", "26379"), ("localhost", "26380")],
        decode_responses=False,
    )
    mock_sentinels.master_for.assert_called_once_with("test_master", db=4)
    assert store == mock_sentinels.master_for.return_value
