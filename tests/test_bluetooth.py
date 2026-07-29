"""Tests for Home Assistant Bluetooth adaptation."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from custom_components.sesame_ble.bluetooth import (
    get_bluetooth_routes,
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


def test_get_bluetooth_routes_returns_each_scanner_sorted_by_rssi() -> None:
    """Expose each connectable scanner path, strongest first."""
    hass = Mock()
    weak = make_service_info(rssi=-78)
    strong = make_service_info(rssi=-48)
    weak_scanner = SimpleNamespace(source="proxy-weak", name="Weak proxy")
    strong_scanner = SimpleNamespace(source="proxy-strong", name="Strong proxy")
    weak_device = Mock(
        scanner=weak_scanner,
        advertisement=weak.advertisement,
        ble_device=weak.device,
    )
    strong_device = Mock(
        scanner=strong_scanner,
        advertisement=strong.advertisement,
        ble_device=strong.device,
    )

    with patch(
        "custom_components.sesame_ble.bluetooth.bluetooth.async_scanner_devices_by_address",
        return_value=[weak_device, strong_device],
    ):
        routes = get_bluetooth_routes(hass, TEST_ADDRESS)

    assert [route.source for route in routes] == ["proxy-strong", "proxy-weak"]
    assert routes[0].name == "Strong proxy"


@pytest.mark.asyncio
async def test_resolver_uses_selected_route() -> None:
    """Resolve the BLE device from the explicitly selected scanner."""
    hass = Mock()
    service_info = make_service_info()
    scanner_device = Mock(
        scanner=Mock(source="proxy-selected", name="Selected proxy"),
        advertisement=service_info.advertisement,
        ble_device=service_info.device,
    )
    def selected_route() -> str:
        return "proxy-selected"

    selected = Mock()

    with patch(
        "custom_components.sesame_ble.bluetooth.bluetooth.async_scanner_devices_by_address",
        return_value=[scanner_device],
    ):
        result = await make_ble_device_resolver(
            hass,
            route_source=selected_route,
            route_selected=selected,
        )(TEST_ADDRESS)

    assert result is not None
    assert result.ble_device is service_info.device
    selected.assert_called_once()
