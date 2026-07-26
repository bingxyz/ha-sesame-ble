"""Tests for the persistent Sesame runtime."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from gomalock import Sesame5MechStatus
from homeassistant.components.bluetooth import BluetoothChange

from custom_components.sesame_ble.runtime import SesameRuntime

from .helpers import TEST_ADDRESS, TEST_SECRET, TEST_UUID, make_service_info


async def test_runtime_connects_and_sends_explicit_commands() -> None:
    """Connect, login, cache status and send lock/unlock commands serially."""
    status = Sesame5MechStatus(2500, 0b00010010, target=0, position=256)
    device = Mock(is_connected=False, is_logged_in=False, mech_status=status)

    async def connect() -> None:
        device.is_connected = True

    async def login() -> None:
        device.is_logged_in = True

    async def disconnect() -> None:
        device.is_connected = False
        device.is_logged_in = False

    device.connect = AsyncMock(side_effect=connect)
    device.login = AsyncMock(side_effect=login)
    device.disconnect = AsyncMock(side_effect=disconnect)
    device.lock = AsyncMock()
    device.unlock = AsyncMock()
    hass = Mock()
    service_info = make_service_info()
    unsubscribe_bluetooth = Mock()

    with (
        patch(
            "custom_components.sesame_ble.runtime.Sesame5",
            return_value=device,
        ),
        patch(
            "custom_components.sesame_ble.runtime.make_ble_device_resolver",
            return_value=Mock(),
        ),
        patch(
            "custom_components.sesame_ble.runtime.make_ble_client_factory",
            return_value=Mock(),
        ),
        patch(
            "custom_components.sesame_ble.runtime.bluetooth.async_last_service_info",
            return_value=service_info,
        ) as last_service_info,
        patch(
            "custom_components.sesame_ble.runtime.bluetooth.async_register_callback",
            return_value=unsubscribe_bluetooth,
        ) as register_callback,
    ):
        runtime = SesameRuntime(
            hass,
            address=TEST_ADDRESS,
            device_uuid=str(TEST_UUID),
            secret_key=TEST_SECRET,
            name="Entrance",
        )

        # The selected connectable route may update while connect/login runs.
        last_service_info.side_effect = [
            service_info,
            make_service_info(rssi=-57),
        ]
        await runtime.async_start()
        last_service_info.side_effect = None
        bluetooth_callback = register_callback.call_args.args[1]
        assert runtime.rssi == -57

        newer_service_info = make_service_info(rssi=-61)
        bluetooth_callback(newer_service_info, BluetoothChange.ADVERTISEMENT)
        assert runtime.rssi == -61

        # HA updates its Bluetooth history for RSSI-only changes without
        # dispatching an integration callback. An operation must refresh that
        # cached value explicitly.
        last_service_info.return_value = make_service_info(rssi=-73)
        await runtime.async_set_locked(locked=False)
        assert runtime.rssi == -73
        await runtime.async_set_locked(locked=True)
        assert runtime.last_operation_action == "lock"
        assert runtime.last_operation_completed_at is not None
        assert runtime.last_operation_duration is not None
        assert runtime.last_operation_result == "success"

        device.unlock.side_effect = TimeoutError
        with (
            patch.object(runtime, "_handle_unexpected_disconnect"),
            pytest.raises(TimeoutError),
        ):
            await runtime.async_set_locked(locked=False)
        assert runtime.last_operation_action == "unlock"
        assert runtime.last_operation_duration is not None
        assert runtime.last_operation_result == "failed"

        await runtime.async_stop()

    assert runtime.available is False
    device.connect.assert_awaited_once_with()
    device.login.assert_awaited_once_with()
    assert device.unlock.await_count == 2
    device.unlock.assert_awaited_with("Home Assistant")
    device.lock.assert_awaited_once_with("Home Assistant")
    assert device.disconnect.await_count == 2
    device.disconnect.assert_awaited_with()
    unsubscribe_bluetooth.assert_called_once_with()
