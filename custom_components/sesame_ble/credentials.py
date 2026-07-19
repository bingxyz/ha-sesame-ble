"""Credential parsing and validation for Sesame BLE."""

import binascii
import struct
from dataclasses import dataclass

from gomalock import OS3QRCode, ProductModel, SesameError

from .const import MODEL_NAME, SUPPORTED_MODEL
from .exceptions import (
    DeviceMismatchError,
    InvalidCredentialsError,
    UnsupportedDeviceError,
)


@dataclass(frozen=True, slots=True)
class SesameCredentials:
    """Validated credentials for one Sesame device."""

    device_name: str
    device_uuid: str
    secret_key: str


def normalize_secret_key(value: str) -> str:
    """Validate and normalize a 16-byte hexadecimal secret key."""
    normalized = value.strip().replace(" ", "").lower()
    try:
        secret = bytes.fromhex(normalized)
    except ValueError as err:
        raise InvalidCredentialsError from err
    if len(secret) != 16:
        raise InvalidCredentialsError
    return secret.hex()


def credentials_from_share_url(
    share_url: str,
    *,
    expected_uuid: str,
    expected_model: ProductModel = SUPPORTED_MODEL,
) -> SesameCredentials:
    """Parse a manager/owner share URL and match it to a discovery."""
    try:
        qr_code = OS3QRCode.from_qr_url(share_url.strip())
    except (
        binascii.Error,
        KeyError,
        SesameError,
        struct.error,
        TypeError,
        ValueError,
    ) as err:
        raise InvalidCredentialsError from err

    if qr_code.product_model is not expected_model:
        raise UnsupportedDeviceError
    if str(qr_code.device_uuid).lower() != expected_uuid.lower():
        raise DeviceMismatchError

    return SesameCredentials(
        device_name=qr_code.device_name.strip() or MODEL_NAME,
        device_uuid=str(qr_code.device_uuid),
        secret_key=qr_code.secret_key.hex(),
    )
