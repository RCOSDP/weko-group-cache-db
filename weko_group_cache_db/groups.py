#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Utils module for weko-group-cache-db."""

import time
import traceback
import typing as t

from datetime import UTC, datetime
from urllib.parse import urljoin

import backoff
import redis
import requests

from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

from .config import config
from .exc import UpdateError
from .loader import Institution, InstitutionSource, load_institutions
from .logger import console, logger
from .redis import connection
from .signals import ExecutedData, ProgressData, executed_signal, progress_signal

if t.TYPE_CHECKING:
    from backoff.types import Details
    from redis import Redis


def fetch_all(**kwargs: t.Unpack[InstitutionSource]):
    """Fetch and cache groups for all institutions.

    Arguments:
        kwargs (InstitutionSource):
            - toml_path (str | Path): Path to the TOML file.
            - directory_path (str | Path): Path to the directory containing TOML files.
            - fqdn_list_file (str | Path): Path to the file containing FQDN list.

    Raises:
        ExceptionGroup:
            If there are failures in updating information from one or more institutions.

    """
    store = connection()
    institutions = load_institutions(**kwargs)
    total = len(institutions)
    exceptions: list[UpdateError] = []

    if total == 0:
        logger.warning("No institutions found to fetch and cache groups for.")
        return

    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Fetching and caching groups for all institutions", total=total
        )

        for index, institution in enumerate(institutions):
            _send_progress_signal(institutions, index)

            try:
                group_count = fetch_and_cache()(institution, store)
                logger.info(
                    "Successfully cached %(count)d groups for %(fqdn)s.",
                    {"count": group_count, "fqdn": institution.fqdn},
                )
            except (requests.RequestException, redis.RedisError) as ex:
                logger.error(
                    "Despite retries %(count)d times, failed to cache groups to Redis "
                    "for institution: %(fqdn)s.",
                    {"count": config.REQUEST_RETRIES, "fqdn": institution.fqdn},
                )
                traceback.print_exc()
                exceptions.append(UpdateError(institution.fqdn, origin=ex))
            finally:
                progress.update(task, advance=1)

            if index != total - 1:
                time.sleep(config.REQUEST_INTERVAL)

    _send_progress_signal(institutions, total)

    if exceptions:
        error_message = "Failed to update information from %d institution(s)."
        logger.error(error_message, len(exceptions))
        raise ExceptionGroup(error_message % len(exceptions), exceptions)


def fetch_one(fqdn: str, **kwargs: t.Unpack[InstitutionSource]) -> None:
    """Fetch and cache groups for a specific institution.

    Arguments:
        fqdn (str): FQDN of the target institution.
        kwargs (InstitutionSource):
            - toml_path (str | Path): Path to the TOML file.
            - directory_path (str | Path): Path to the directory containing TOML files.
            - fqdn_list_file (str | Path): Path to the file containing FQDN list.

    Raises:
        ValueError: If the institution with the given FQDN is not found.
        UpdateError: If fetching or caching groups fails.

    """
    store = connection()
    institutions = load_institutions(**kwargs)

    target_institution = next(
        (inst for inst in institutions if inst.fqdn == fqdn), None
    )

    if target_institution is None:
        error_message = "Institution with FQDN %s not found."
        logger.error(error_message, fqdn)
        raise ValueError(error_message % fqdn)

    with console.status(f"Fetching and caching groups for institution: {fqdn}"):
        try:
            group_count = fetch_and_cache()(target_institution, store)
            logger.info("Successfully cached %d groups for %s.", group_count, fqdn)
        except (requests.RequestException, redis.RedisError) as ex:
            logger.error(
                "Despite retries %(count)d times, failed to cache groups to Redis "
                "for institution: %(fqdn)s.",
                {"count": config.REQUEST_RETRIES, "fqdn": target_institution.fqdn},
            )
            raise UpdateError(fqdn, origin=ex) from ex


def fetch_and_cache():
    """Return a function that fetches and caches groups with retries.

    Returns:
        Callable[[Institution,Redis],int]:
            A function that takes an Institution and Redis store,
            fetches groups from the mAP API, and caches them in Redis with retries.

    """

    def _count(details: Details) -> None:
        """Update the retry count based on backoff details.

        Arguments:
            details (Details): Details from backoff.

        """
        nonlocal retries
        retries = details.get("tries", 0)

    @backoff.on_exception(
        lambda: backoff.expo(
            base=config.REQUEST_RETRY_BASE,
            factor=config.REQUEST_RETRY_FACTOR,
            max_value=config.REQUEST_RETRY_MAX,
        ),
        (requests.RequestException, redis.RedisError),
        max_tries=config.REQUEST_RETRIES + 1,
        jitter=backoff.full_jitter,
        on_backoff=_count,
    )
    def _retrieve_fetch_and_cache(institution: Institution, store: Redis) -> int:
        nonlocal retries
        try:
            group_ids = fetch_map_groups(institution)
            updated_at = set_groups_to_redis(institution.fqdn, group_ids, store=store)
            _send_executed_signal(
                institution, "success", retries=retries, updated_at=updated_at
            )
            return len(group_ids)
        except requests.RequestException as ex:
            logger.warning(
                "Failed to fetch groups from mAP API for institution: %s",
                institution.fqdn,
            )
            _send_executed_signal(institution, "failed", retries=retries, error=ex)
            raise
        except redis.RedisError as ex:
            logger.warning(
                "Failed to cache groups to Redis for institution: %s",
                institution.fqdn,
            )
            _send_executed_signal(institution, "failed", retries=retries, error=ex)
            raise

    retries = 0
    return _retrieve_fetch_and_cache


def fetch_map_groups(institution: Institution) -> list[str]:
    """Fetch and cache groups for the given institution.

    Arguments:
        institution (Institution): Institution object.

    Returns:
        list[str]: List of group IDs.

    """
    endpoint = urljoin(config.MAP_GROUPS_API_ENDPOINT, institution.sp_connector_id)

    response = requests.get(
        endpoint,
        cert=(institution.client_cert_path, institution.client_key_path),
        timeout=config.REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    group_entries = response.json().get("entry", [])

    group_ids: list[str] = [
        group["id"].split("/")[-1] for group in group_entries if "id" in group
    ]

    return group_ids


def set_groups_to_redis(
    fqdn: str, group_ids: list[str], *, store: Redis | None = None
) -> datetime:
    """Set groups to redis.

    Arguments:
        fqdn(str): fqdn of the target sp
        group_ids(list[str]): list of group ids
        store(Redis | None):
            Redis store object. If None, a new connection will be established.

    Returns:
        datetime: The timestamp when the groups were cached.

    """
    redis_key = cache_key(fqdn)
    now = datetime.now(UTC)
    updated_at = now.isoformat(timespec="seconds")

    if store is None:
        store = connection()

    store.hset(
        redis_key, mapping={"updated_at": updated_at, "groups": ",".join(group_ids)}
    )
    store.persist(redis_key)
    if config.CACHE_TTL >= 0:
        store.expire(redis_key, config.CACHE_TTL)

    return now


def cache_key(fqdn: str) -> str:
    """Generate the Redis key for the given FQDN.

    Arguments:
        fqdn (str): FQDN of the institution.

    Returns:
        str: Redis key for the institution's groups.

    """
    transformed_fqdn = fqdn.replace(".", "_").replace("-", "_")
    return transformed_fqdn + config.CACHE_KEY_SUFFIX


def _send_progress_signal(institutions: list[Institution], index: int) -> None:
    total = len(institutions)
    if index >= total:
        status = "completed"
    elif index > 0:
        status = "in_progress"
    else:
        status = "started"
    current = institutions[index].fqdn if index < total else "N/A"

    data = ProgressData(status=status, total=total, done=index, current=current)

    try:
        progress_signal.send(fetch_all, data=data)
    except Exception:  # noqa: BLE001
        traceback.print_exc()


def _send_executed_signal(
    institution: Institution,
    status: t.Literal["success", "failed"],
    updated_at: datetime | None = None,
    retries: int = 0,
    error: Exception | None = None,
) -> None:
    data = ExecutedData(
        fqdn=institution.fqdn,
        status=status,
        retries=retries,
        error_type=type(error).__name__ if error else None,
        error_message=str(error) if error else None,
        updated_at=updated_at or datetime.now(UTC),
    )

    try:
        executed_signal.send(fetch_all, data=data)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
