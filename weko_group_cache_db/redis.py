#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Redis connection module for weko-group-cache-db."""

from redis import Redis, sentinel
from redis.exceptions import ConnectionError as RedisConnectionError

from .config import config
from .logger import logger


def connection() -> Redis:
    """Establish Redis connection.

    Returns:
        Redis: Redis store object.

    Raises:
        ValueError: If configuration for Redis is invalid.
        ConnectionError: If failed to connect to Redis.

    """
    try:  # ruff: ignore[too-many-statements-in-try-clause]
        if config.REDIS_TYPE == "RedisCache":
            store = _redis_connection()
            store.ping()
            logger.info("Successfully connected to Redis.")
        else:
            store = _sentinel_connection()
            store.ping()
            logger.info("Successfully connected to Redis Sentinel.")
    except ValueError:
        logger.error("Failed to connect to Redis. Invalid configuration.")
        raise
    except RedisConnectionError:
        logger.error("Failed to connect to Redis. Something went wrong on Redis.")
        raise

    return store


def _redis_connection() -> Redis:
    """Establish Redis connection and return Redis store object.

    Returns:
    Redis: Redis store object.

    """
    redis_url = config.REDIS_URL
    return Redis.from_url(redis_url)


def _sentinel_connection() -> Redis:
    """Establish Redis sentinel connection.

    Returns:
        Redis: Redis store object

    """
    sentinels = sentinel.Sentinel(config.REDIS_SENTINELS, decode_responses=False)
    return sentinels.master_for(config.REDIS_SENTINEL_MASTER, db=config.REDIS_DB_INDEX)
