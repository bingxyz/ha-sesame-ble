"""Tests for Home Assistant Bluetooth adaptation."""

from unittest.mock import Mock, patch

import pytest

from custom_components.sesame_ble.bluetooth import (
    make_ble_device_resolver,
    parse_sesame_advertisement,
)

from .helpers import TEST_ADDRESS, TEST_UUID, make_service_info


def test_parse_supported_advertisement() -> None:
    """Parse SESAME 5 Pro model, registration and UUID."""
    advertisement = parse_sesame_advertisement(make_service_info())

    assert advertisement is not None
    assert advertisement.device_uuid == TEST_UUID
    assert advertisement.is_registered is True


@pytest.mark.parametrize("model", [5, 16, 25])
def test_filter_unsupported_models(model: int) -> None:
    """Ignore other devices sharing the Sesame service UUID."""
    assert parse_sesame_advertisement(make_service_info(model=model)) is None


@pytest.mark.asyncio
async def test_resolver_uses_current_ha_route() -> None:
    """Resolve the current BLEDevice and matching advertisement from HA."""
    hass = Mock()
    service_info = make_service_info()
    with (
        patch(
            "custom_components.sesame_ble.bluetooth.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ) as get_device,
        patch(
            "custom_components.sesame_ble.bluetooth.bluetooth.async_last_service_info",
            return_value=service_info,
        ) as get_info,
    ):
        result = await make_ble_device_resolver(hass)(TEST_ADDRESS)

    assert result is not None
    assert result.ble_device is service_info.device
    assert result.advertisement_data.device_uuid == TEST_UUID
    get_device.assert_called_once_with(hass, TEST_ADDRESS, connectable=True)
    get_info.assert_called_once_with(hass, TEST_ADDRESS, connectable=True)
