"""Tests for lock, angle and battery entities."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from gomalock import Sesame5MechStatus

from custom_components.sesame_ble.lock import SesameLockEntity
from custom_components.sesame_ble.sensor import SENSORS, SesameSensor

from .helpers import TEST_ADDRESS, TEST_UUID


def make_runtime(*, flags: int, position: int = 256) -> SimpleNamespace:
    """Build the cached runtime surface consumed by entities."""
    return SimpleNamespace(
        address=TEST_ADDRESS,
        device_uuid=str(TEST_UUID),
        name="Entrance",
        available=True,
        pending_locked=None,
        mech_status=Sesame5MechStatus(2500, flags, target=0, position=position),
        async_add_listener=lambda _listener: lambda: None,
        async_set_locked=AsyncMock(),
    )


def test_lock_and_sensor_state() -> None:
    """Map calibrated range, raw angle and battery values."""
    runtime = make_runtime(flags=0b00010010)
    lock = SesameLockEntity(runtime)
    sensors = {
        description.key: SesameSensor(runtime, description) for description in SENSORS
    }

    assert lock.is_locked is True
    assert lock.is_jammed is False
    assert sensors["angle"].native_value == 90.0
    assert sensors["battery"].native_value is not None
    assert sensors["battery_voltage"].native_value == 5.0


def test_unlock_and_jammed_state() -> None:
    """Map unlock range and clutch failure flags."""
    runtime = make_runtime(flags=0b00010101)
    lock = SesameLockEntity(runtime)

    assert lock.is_locked is False
    assert lock.is_jammed is True


async def test_explicit_lock_and_unlock_commands() -> None:
    """Use explicit desired state instead of an unsafe toggle."""
    runtime = make_runtime(flags=0b00010010)
    lock = SesameLockEntity(runtime)

    await lock.async_unlock()
    await lock.async_lock()

    assert runtime.async_set_locked.await_args_list[0].kwargs == {"locked": False}
    assert runtime.async_set_locked.await_args_list[1].kwargs == {"locked": True}
