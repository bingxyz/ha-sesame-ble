"""Runtime connection and state management for Sesame BLE."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import cast

from gomalock import Sesame5, Sesame5MechStatus
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.core import HomeAssistant, callback

from .bluetooth import make_ble_client_factory, make_ble_device_resolver
from .const import RECONNECT_MAX_DELAY

_LOGGER = logging.getLogger(__name__)


class SesameRuntime:
    """Own one persistent Sesame connection and its Home Assistant state."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        address: str,
        device_uuid: str,
        secret_key: str,
        name: str,
    ) -> None:
        """Initialize a runtime without performing I/O."""
        self.hass = hass
        self.address = address
        self.device_uuid = device_uuid
        self.name = name
        self.available = False
        self.mech_status: Sesame5MechStatus | None = None
        self.pending_locked: bool | None = None
        self.rssi: int | None = None

        self._listeners: set[Callable[[], None]] = set()
        self._operation_lock = asyncio.Lock()
        self._reconnect_task: asyncio.Task[None] | None = None
        self._unsubscribe_bluetooth: Callable[[], None] | None = None
        self._stopping = False
        self.device = Sesame5(
            address,
            secret_key=secret_key,
            mech_status_callback=self._handle_mech_status,
            unexpected_disconnect_callback=self._handle_unexpected_disconnect,
            reconnect_attempts=0,
            ble_device_resolver=make_ble_device_resolver(hass),
            ble_client_factory=make_ble_client_factory(name),
        )

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register an entity state listener."""
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return cast(Callable[[], None], remove_listener)

    @callback
    def _notify_listeners(self) -> None:
        """Notify all entities that cached state changed."""
        for listener in tuple(self._listeners):
            listener()

    @callback
    def _handle_mech_status(
        self,
        _device: Sesame5,
        status: Sesame5MechStatus,
    ) -> None:
        """Store a mechanical-status publish from gomalock."""
        self.mech_status = status
        self.available = True
        self._notify_listeners()

    @callback
    def _handle_bluetooth_advertisement(
        self,
        service_info: BluetoothServiceInfoBleak,
        _change: BluetoothChange,
    ) -> None:
        """Store signal strength from the latest connectable advertisement."""
        if service_info.rssi == self.rssi:
            return
        self.rssi = service_info.rssi
        self._notify_listeners()

    @callback
    def _handle_unexpected_disconnect(self, _device: Sesame5) -> None:
        """Mark unavailable and schedule a fresh HA-routed connection."""
        self.available = False
        self.mech_status = None
        self.pending_locked = None
        self._notify_listeners()
        if self._stopping:
            return
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = self.hass.async_create_task(
                self._async_reconnect(),
                f"Reconnect {self.name}",
            )

    async def async_start(self) -> None:
        """Connect and authenticate the persistent session."""
        self._stopping = False
        service_info = bluetooth.async_last_service_info(
            self.hass,
            self.address,
            connectable=True,
        )
        if service_info is not None:
            self.rssi = service_info.rssi
        if self._unsubscribe_bluetooth is None:
            self._unsubscribe_bluetooth = bluetooth.async_register_callback(
                self.hass,
                self._handle_bluetooth_advertisement,
                {"address": self.address, "connectable": True},
                BluetoothScanningMode.PASSIVE,
            )
        async with self._operation_lock:
            await self._async_connect_locked()

    async def _async_connect_locked(self) -> None:
        """Connect while the caller holds the operation lock."""
        if not self.device.is_connected:
            await self.device.connect()
        if not self.device.is_logged_in:
            await self.device.login()
        self.mech_status = self.device.mech_status
        self.available = True
        self._notify_listeners()

    async def _async_reconnect(self) -> None:
        """Reconnect forever with bounded exponential backoff until stopped."""
        attempt = 0
        while not self._stopping:
            delay = min(2**attempt, RECONNECT_MAX_DELAY)
            await asyncio.sleep(delay)
            if self._stopping:
                return
            try:
                async with self._operation_lock:
                    await self._async_connect_locked()
            except asyncio.CancelledError:
                raise
            except Exception:
                attempt += 1
                _LOGGER.warning(
                    "Unable to reconnect to %s; retrying in at most %.0f seconds",
                    self.name,
                    RECONNECT_MAX_DELAY,
                    exc_info=True,
                )
            else:
                _LOGGER.info("Reconnected to %s", self.name)
                return

    async def async_set_locked(self, *, locked: bool) -> None:
        """Send an explicit desired lock state without blind command replay."""
        async with self._operation_lock:
            if not self.device.is_logged_in:
                await self._async_connect_locked()
            self.pending_locked = locked
            self._notify_listeners()
            try:
                if locked:
                    await self.device.lock("Home Assistant")
                else:
                    await self.device.unlock("Home Assistant")
            except Exception:
                self.available = False
                try:
                    await self.device.disconnect()
                finally:
                    self._handle_unexpected_disconnect(self.device)
                raise
            finally:
                self.pending_locked = None
                self._notify_listeners()

    async def async_stop(self) -> None:
        """Stop reconnect work and close the BLE connection."""
        self._stopping = True
        unsubscribe_bluetooth = self._unsubscribe_bluetooth
        self._unsubscribe_bluetooth = None
        if unsubscribe_bluetooth is not None:
            unsubscribe_bluetooth()
        reconnect_task = self._reconnect_task
        self._reconnect_task = None
        if reconnect_task is not None and not reconnect_task.done():
            reconnect_task.cancel()
            with suppress(asyncio.CancelledError):
                await reconnect_task
        async with self._operation_lock:
            await self.device.disconnect()
        self.available = False
        self.mech_status = None
        self.pending_locked = None
        self._notify_listeners()
