#
# Copyright (C) 2025 National Institute of Informatics.
#

"""File loader module for weko-group-cache-db."""

import tomllib
import traceback
import typing as t

from pathlib import Path
from tomllib import TOMLDecodeError

import inflect

from pydantic import BaseModel, ConfigDict, Field
from pydantic_core import ValidationError
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

from .config import config
from .exc import ConfigurationError
from .logger import console, logger


class InstitutionSource(t.TypedDict):
    """Source configuration for loading institution information."""

    toml_path: t.NotRequired[str | Path]
    """Path to the TOML file."""

    directory_path: t.NotRequired[str | Path]
    """Path to the directory containing TOML files."""

    fqdn_list_file: t.NotRequired[str | Path]
    """Path to the file containing FQDN list."""

    fqdn_list: t.NotRequired[list[str]]
    """List of FQDNs."""


def load_institutions(**kwargs: t.Unpack[InstitutionSource]) -> list[Institution]:
    """Load institution information from the configured source.

    Arguments:
        kwargs (InstitutionSource):
            Source configuration for loading institution information.

    Returns:
        list[Institution]: List of Institution objects.

    """
    if "toml_path" in kwargs:
        return load_institutions_from_toml(kwargs["toml_path"])
    if "directory_path" in kwargs and "fqdn_list_file" in kwargs:
        return load_institutions_from_directory(
            kwargs["directory_path"], kwargs["fqdn_list_file"]
        )
    if "directory_path" in kwargs and "fqdn_list" in kwargs:
        return load_institutions_from_list(
            kwargs["directory_path"], kwargs["fqdn_list"]
        )
    logger.error("Invalid institution source configuration.")
    return []


def load_institutions_from_toml(toml_path: str | Path) -> list[Institution]:
    """Load institution information from TOML file.

    Arguments:
        toml_path (Path): Path to the TOML file.

    Returns:
        list[Institution]: List of Institution objects.

    Raises:
        ConfigurationError: If the TOML file cannot be read or is invalid.

    """
    if isinstance(toml_path, str):
        toml_path = Path(toml_path)

    with console.status("Loading institutions from TOML file"):
        try:
            with toml_path.open("rb") as f:
                toml_data = tomllib.load(f)
        except FileNotFoundError as ex:
            error_message = "TOML file not found: %s"
            logger.error(error_message, toml_path)
            raise ConfigurationError(error_message % toml_path) from ex
        except (TOMLDecodeError, ValueError) as ex:
            error_message = "Failed to load TOML file: %s"
            logger.error(error_message, toml_path)
            raise ConfigurationError(error_message % toml_path) from ex

        if "institutions" not in toml_data:
            logger.error("No 'institutions' section found in the TOML file.")
            return []

        if not isinstance(toml_data["institutions"], list):
            logger.error("The 'institutions' section must be a list in the TOML file.")
            return []

    p = inflect.engine()
    institutions: list[Institution] = []
    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Validating institution entries...", total=len(toml_data["institutions"])
        )
        for index, item in enumerate(toml_data["institutions"]):
            ordinal = p.ordinal(index + 1)  # pyright: ignore[reportArgumentType]

            try:
                institution = Institution.model_validate(item)
            except ValidationError:
                institution_fqdn = item.get("fqdn", "Unknown")
                logger.warning(
                    'Failed to load %(ordinal)s institution "%(fqdn)s".',
                    {"ordinal": ordinal, "fqdn": institution_fqdn},
                )
                traceback.print_exc()
                continue
            else:
                if not check_existence_file(institution):
                    logger.warning(
                        'Skip %(ordinal)s institution "%(fqdn)s" '
                        "due to missing TLS client cert/key files.",
                        {"ordinal": ordinal, "fqdn": institution.fqdn},
                    )
                    continue

                institutions.append(institution)
            finally:
                progress.update(task, advance=1)

    logger.info("%d institutions loaded successfully.", len(institutions))

    return institutions


CRT_FILE_NAME = "server.crt"
"""File name for TLS client certificate in directory source."""

KEY_FILE_NAME = "server.key"
"""File name for TLS client key in directory source."""


def load_institutions_from_directory(
    directory_path: str | Path, fqdn_list_file: str | Path
) -> list[Institution]:
    """Load institution information from the configured directory.

    Arguments:
        directory_path (str | Path):
            Path to the directory containing TOML files.
        fqdn_list_file (str | Path):
            Path to the file containing FQDN list

    Returns:
        list[Institution]: List of Institution objects.

    """
    if isinstance(fqdn_list_file, str):
        fqdn_list_file = Path(fqdn_list_file)

    with fqdn_list_file.open("r", encoding="utf-8") as f:
        fqdn_list = [
            L.split(" ")[0]
            for line in f
            if (L := line.strip()) and not L.startswith("#")
        ]
    return load_institutions_from_list(directory_path, fqdn_list)


def load_institutions_from_list(
    directory_path: str | Path, fqdn_list: list[str]
) -> list[Institution]:
    """Load institution information from the provided FQDN list.

    Arguments:
        directory_path (str | Path): Path to the directory containing TOML files.
        fqdn_list (list[str]): List of FQDNs.

    Returns:
        list[Institution]: List of Institution objects.

    """
    if isinstance(directory_path, str):
        directory_path = Path(directory_path)

    p = inflect.engine()
    institutions: list[Institution] = []
    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Loading institutions from directory...", total=len(fqdn_list)
        )
        for index, fqdn in enumerate(fqdn_list):
            ordinal = p.ordinal(index + 1)  # pyright: ignore[reportArgumentType]

            sp_connector_id = (
                f"{config.SP_CONNECTOR_ID_PREFIX}"
                f"{fqdn.replace('.', '_').replace('-', '_')}"
            )
            client_cert_path = directory_path / fqdn / CRT_FILE_NAME
            client_key_path = directory_path / fqdn / KEY_FILE_NAME

            try:
                institution = Institution(
                    name=None,
                    fqdn=fqdn,
                    sp_connector_id=sp_connector_id,
                    client_cert_path=str(client_cert_path),
                    client_key_path=str(client_key_path),
                )
            except ValidationError:
                logger.warning(
                    'Failed to load %(ordinal)s institution "%(fqdn)s".',
                    {"ordinal": ordinal, "fqdn": fqdn},
                )
                traceback.print_exc()
                continue
            else:
                if not check_existence_file(institution):
                    logger.warning(
                        'Skip %(ordinal)s institution "%(fqdn)s" due to missing '
                        "TLS client cert/key files.",
                        {"ordinal": ordinal, "fqdn": institution.fqdn},
                    )
                    continue
                institutions.append(institution)
            finally:
                progress.update(task, advance=1)

    logger.info("%d institutions loaded successfully.", len(institutions))

    return institutions


def check_existence_file(institution: Institution) -> bool:
    """Check existence of TLS client cert and key files.

    Arguments:
        institution (Institution): Institution object.

    Returns:
        bool: True if both files exist, False otherwise.

    """
    cert_path = Path(institution.client_cert_path)
    key_path = Path(institution.client_key_path)

    return cert_path.exists() and key_path.exists()


class Institution(BaseModel):
    """Institution model for loading from TOML file."""

    name: str | None = None
    """Name of the institution. Optional."""

    fqdn: str
    """FQDN of the institution."""

    sp_connector_id: str = Field(..., validation_alias="spid")
    """Service Provider Connector ID of the institution."""

    client_cert_path: str = Field(..., validation_alias="cert")
    """Path to TLS client certificate file."""

    client_key_path: str = Field(..., validation_alias="key")
    """Path to TLS client key file."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_by_name=True,
        validate_by_alias=True,
    )
