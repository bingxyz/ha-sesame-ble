"""Home Assistant Bluetooth adapters for gomalock."""

import struct
from collections.abc import Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from gomalock import (
    BLEClientFactory,
    BLEDeviceResolver,
    ProductModel,
    ScannedSesameWithBLE,
    Sesame5,
    SesameAdvertisementData,
)
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant

from .const import COMPANY_ID, MODEL_NAME, SUPPORTED_MODEL


def parse_sesame_advertisement(
    service_info: BluetoothServiceInfoBleak,
) -> SesameAdvertisementData | None:
    """Parse a supported Sesame advertisement received by Home Assistant."""
    manufacturer_data = service_info.manufacturer_data.get(COMPANY_ID)
    if manufacturer_data is None:
        return None
    try:
        advertisement = SesameAdvertisementData.from_manufacturer_data(
            manufacturer_data
        )
    except ValueError, struct.error:
        return None
    if advertisement.product_model is not SUPPORTED_MODEL:
        return None
    return advertisement


def make_ble_device_resolver(hass: HomeAssistant) -> BLEDeviceResolver:
    """Create a resolver that asks HA for a fresh connectable route each time."""

    async def resolve(address: str) -> ScannedSesameWithBLE | None:
        ble_device = bluetooth.async_ble_device_from_address(
            hass,
            address.upper(),
            connectable=True,
        )
        service_info = bluetooth.async_last_service_info(
            hass,
            address.upper(),
            connectable=True,
        )
        if ble_device is None or service_info is None:
            return None
        advertisement = parse_sesame_advertisement(service_info)
        if advertisement is None:
            return None
        return ScannedSesameWithBLE(
            service_info.address,
            advertisement,
            ble_device,
        )

    return resolve


def make_ble_client_factory(name: str = MODEL_NAME) -> BLEClientFactory:
    """Create a Bleak Retry Connector client factory."""

    async def connect(
        ble_device: BLEDevice,
        disconnected_callback: Callable[[BleakClient], None],
    ) -> BleakClient:
        return await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            name,
            disconnected_callback=disconnected_callback,
            max_attempts=3,
        )

    return connect


async def async_validate_connection(
    hass: HomeAssistant,
    *,
    address: str,
    secret_key: str,
) -> None:
    """Connect and authenticate once without retaining the BLE connection."""
    device = Sesame5(
        address,
        secret_key=secret_key,
        reconnect_attempts=0,
        ble_device_resolver=make_ble_device_resolver(hass),
        ble_client_factory=make_ble_client_factory(),
    )
    try:
        await device.connect()
        await device.login()
    finally:
        await device.disconnect()


def is_supported_model(product_model: ProductModel) -> bool:
    """Return whether the model is enabled by this integration release."""
    return product_model is SUPPORTED_MODEL
