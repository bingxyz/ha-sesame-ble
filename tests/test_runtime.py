"""Tests for the persistent Sesame runtime."""

from unittest.mock import AsyncMock, Mock, patch

from gomalock import Sesame5MechStatus

from custom_components.sesame_ble.runtime import SesameRuntime

from .helpers import TEST_ADDRESS, TEST_SECRET, TEST_UUID


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
    ):
        runtime = SesameRuntime(
            hass,
            address=TEST_ADDRESS,
            device_uuid=str(TEST_UUID),
            secret_key=TEST_SECRET,
            name="Entrance",
        )

    await runtime.async_start()
    await runtime.async_set_locked(locked=False)
    await runtime.async_set_locked(locked=True)
    await runtime.async_stop()

    assert runtime.available is False
    device.connect.assert_awaited_once_with()
    device.login.assert_awaited_once_with()
    device.unlock.assert_awaited_once_with("Home Assistant")
    device.lock.assert_awaited_once_with("Home Assistant")
    device.disconnect.assert_awaited_once_with()
