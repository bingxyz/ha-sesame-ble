"""Test helpers for Sesame BLE."""

import struct
import time
from uuid import UUID

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from custom_components.sesame_ble.const import COMPANY_ID, SESAME_SERVICE_UUID

TEST_ADDRESS = "AA:BB:CC:DD:EE:FF"
TEST_UUID = UUID("01234567-89ab-cdef-0123-456789abcdef")
TEST_SECRET = "00112233445566778899aabbccddeeff"


def make_service_info(
    *,
    model: int = 7,
    registered: bool = True,
    device_uuid: UUID = TEST_UUID,
    connectable: bool = True,
    rssi: int = -52,
) -> BluetoothServiceInfoBleak:
    """Build a realistic Sesame advertisement for tests."""
    manufacturer_data = struct.pack(
        "<HB16s",
        model,
        int(registered),
        device_uuid.bytes,
    )
    device = BLEDevice(TEST_ADDRESS, "SESAME", details={})
    advertisement = AdvertisementData(
        local_name="SESAME",
        manufacturer_data={COMPANY_ID: manufacturer_data},
        service_data={},
        service_uuids=[SESAME_SERVICE_UUID],
        tx_power=None,
        rssi=rssi,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak.from_device_and_advertisement_data(
        device,
        advertisement,
        "proxy-a",
        time.monotonic(),
        connectable,
    )
