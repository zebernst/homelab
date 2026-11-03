"""Load modem-pdu-cycle config from Fission-mounted secret files.

ExternalSecret keys (e.g. ``unifi.url``) become files under
``/secrets/fission/<mount>/``. pydantic-settings NestedSecretsSettingsSource
maps those dotted filenames onto nested models.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import BaseModel, SecretStr
from pydantic_settings import (
    BaseSettings,
    NestedSecretsSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class WebhookSettings(BaseModel):
    token: SecretStr


class UnifiSettings(BaseModel):
    url: str = "https://unifi"
    username: str
    password: SecretStr
    site: str = "default"


class PduSettings(BaseModel):
    mac: str
    modem_outlet_index: int
    off_seconds: float = 5.0


class Settings(BaseSettings):
    webhook: WebhookSettings
    unifi: UnifiSettings
    pdu: PduSettings

    model_config = SettingsConfigDict(
        # Match ExternalSecret / Fission secret key filenames (unifi.url, …).
        secrets_nested_delimiter=".",
        # Optional local/dev override: UNIFI__URL, PDU__OUTLET_INDEX, …
        env_nested_delimiter="__",
        secrets_dir_missing="error",
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
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            NestedSecretsSettingsSource(file_secret_settings),
        )

    @classmethod
    def from_fission_secrets(cls, root: Path | str = "/secrets/fission") -> Self:
        """Resolve Fission's hashed mount dir and load settings from it."""
        root_path = Path(root)
        if not root_path.is_dir():
            raise FileNotFoundError(f"missing secrets root: {root_path}")
        # Fission mounts at /secrets/<ns>/<hash>/ — one child dir per secret.
        try:
            secrets_dir = next(root_path.iterdir())
        except StopIteration as exc:
            raise FileNotFoundError(f"empty secrets root: {root_path}") from exc
        return cls(_secrets_dir=secrets_dir)
