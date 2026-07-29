"""Constants for the Sesame BLE integration."""

from typing import Final

from gomalock import ProductModel
from homeassistant.const import Platform

DOMAIN: Final = "sesame_ble"

CONF_DEVICE_UUID: Final = "device_uuid"
CONF_SECRET_KEY: Final = "secret_key"
CONF_SHARE_URL: Final = "share_url"
AUTO_ROUTE_SOURCE: Final = "auto"

COMPANY_ID: Final = 0x055A
SESAME_SERVICE_UUID: Final = "0000fd81-0000-1000-8000-00805f9b34fb"
SUPPORTED_MODEL: Final = ProductModel.SESAME_5_PRO
MODEL_NAME: Final = "SESAME 5 Pro"

PLATFORMS: Final = [
    Platform.LOCK,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.BUTTON,
]

ANGLE_SCALE: Final = 360 / 1024
RECONNECT_MAX_DELAY: Final = 60.0
