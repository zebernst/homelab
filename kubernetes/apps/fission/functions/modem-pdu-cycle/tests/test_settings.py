from pathlib import Path

import pytest
from pydantic import ValidationError

from settings import Settings


def _write_secrets(dir_path: Path, **files: str) -> None:
    for name, value in files.items():
        (dir_path / name).write_text(value)


def test_from_fission_secrets_loads_dotted_keys(tmp_path: Path):
    mount = tmp_path / "abc123"
    mount.mkdir()
    _write_secrets(
        mount,
        **{
            "webhook.token": "tok\n",
            "unifi.username": "admin",
            "unifi.password": "s3cret",
            "pdu.mac": "aa:bb:cc:dd:ee:ff",
            "pdu.outlet_index": "7",
        },
    )

    cfg = Settings.from_fission_secrets(tmp_path)

    assert cfg.webhook.token.get_secret_value() == "tok"
    assert cfg.unifi.url == "https://unifi"
    assert cfg.unifi.username == "admin"
    assert cfg.unifi.password.get_secret_value() == "s3cret"
    assert cfg.unifi.site == "default"
    assert cfg.pdu.mac == "aa:bb:cc:dd:ee:ff"
    assert cfg.pdu.outlet_index == 7
    assert cfg.pdu.off_seconds == 5.0


def test_missing_required_secret_raises(tmp_path: Path):
    mount = tmp_path / "abc123"
    mount.mkdir()
    _write_secrets(
        mount,
        **{
            "webhook.token": "tok",
            "unifi.username": "admin",
            # password missing
            "pdu.mac": "aa:bb:cc:dd:ee:ff",
            "pdu.outlet_index": "1",
        },
    )

    with pytest.raises(ValidationError):
        Settings.from_fission_secrets(tmp_path)


def test_missing_secrets_root_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        Settings.from_fission_secrets(tmp_path / "nope")
