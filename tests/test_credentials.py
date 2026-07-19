"""Tests for QR and manual Sesame credentials."""

from uuid import UUID

import pytest
from gomalock import KeyLevel, OS3QRCode, ProductModel

from custom_components.sesame_ble.credentials import (
    credentials_from_share_url,
    normalize_secret_key,
)
from custom_components.sesame_ble.exceptions import (
    DeviceMismatchError,
    InvalidCredentialsError,
    UnsupportedDeviceError,
)

from .helpers import TEST_SECRET, TEST_UUID


def make_share_url(
    *,
    device_uuid: UUID = TEST_UUID,
    model: ProductModel = ProductModel.SESAME_5_PRO,
) -> str:
    """Build an official-format manager share URL."""
    return OS3QRCode(
        "Entrance",
        KeyLevel.MANAGER,
        model,
        device_uuid,
        bytes.fromhex(TEST_SECRET),
    ).qr_url


def test_normalize_secret_key() -> None:
    """Normalize mixed-case hexadecimal input."""
    assert normalize_secret_key(TEST_SECRET.upper()) == TEST_SECRET


@pytest.mark.parametrize("value", ["", "abcd", "gg" * 16, "00" * 17])
def test_reject_invalid_secret_key(value: str) -> None:
    """Reject malformed or incorrectly sized secrets."""
    with pytest.raises(InvalidCredentialsError):
        normalize_secret_key(value)


def test_parse_share_url() -> None:
    """Extract matching UUID, name and secret from a manager URL."""
    credentials = credentials_from_share_url(
        make_share_url(),
        expected_uuid=str(TEST_UUID),
    )

    assert credentials.device_name == "Entrance"
    assert credentials.device_uuid == str(TEST_UUID)
    assert credentials.secret_key == TEST_SECRET


def test_reject_share_url_for_another_device() -> None:
    """Do not accept a valid key for another nearby lock."""
    with pytest.raises(DeviceMismatchError):
        credentials_from_share_url(
            make_share_url(device_uuid=UUID(int=1)),
            expected_uuid=str(TEST_UUID),
        )


def test_reject_share_url_for_unsupported_model() -> None:
    """Keep the first release scoped to SESAME 5 Pro."""
    with pytest.raises(UnsupportedDeviceError):
        credentials_from_share_url(
            make_share_url(model=ProductModel.SESAME_5),
            expected_uuid=str(TEST_UUID),
        )
