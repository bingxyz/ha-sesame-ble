"""Runtime connection and state management for Sesame BLE."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from time import monotonic
from typing import cast

from bleak.exc import BleakError
from gomalock import Sesame5, Sesame5MechStatus
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.core import HomeAssistant, callback

from .bluetooth import (
    BluetoothRoute,
    get_bluetooth_routes,
    make_ble_client_factory,
    make_ble_device_resolver,
)
from .const import AUTO_ROUTE_SOURCE, RECONNECT_MAX_DELAY

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
        self.last_operation_action: str | None = None
        self.last_operation_completed_at: datetime | None = None
        self.last_operation_duration: float | None = None
        self.last_operation_result: str | None = None
        self.selected_route_source: str | None = None
        self.active_route: BluetoothRoute | None = None

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
            ble_device_resolver=make_ble_device_resolver(
                hass,
                route_source=lambda: self.selected_route_source,
                route_selected=self._handle_route_selected,
            ),
            ble_client_factory=make_ble_client_factory(name),
        )

    @property
    def bluetooth_routes(self) -> tuple[BluetoothRoute, ...]:
        """Return the currently discovered connectable routes."""
        return get_bluetooth_routes(self.hass, self.address)

    @property
    def route_options(self) -> list[str]:
        """Return automatic and currently discovered route labels."""
        routes = self.bluetooth_routes
        options = [AUTO_ROUTE_SOURCE, *(self._route_label(route) for route in routes)]
        if (
            self.selected_route_source
            and self.selected_route_source not in {route.source for route in routes}
        ):
            options.append(self.selected_route_source)
        return options

    @staticmethod
    def _route_label(route: BluetoothRoute) -> str:
        """Return a stable, informative route option label."""
        return f"{route.name} [{route.source}]"

    @property
    def selected_route_option(self) -> str:
        """Return the select option representing the configured route."""
        if self.selected_route_source is None:
            return AUTO_ROUTE_SOURCE
        for route in self.bluetooth_routes:
            if route.source == self.selected_route_source:
                return self._route_label(route)
        return self.selected_route_source

    def select_route_option(self, option: str) -> None:
        """Store the source represented by a route select option."""
        if option == AUTO_ROUTE_SOURCE:
            self.async_select_route(option)
            return
        for route in self.bluetooth_routes:
            if self._route_label(route) == option:
                self.async_select_route(route.source)
                return
        if option in self.route_options:
            self.async_select_route(option)
            return
        raise ValueError(f"Unknown Bluetooth route: {option}")

    @callback
    def _handle_route_selected(self, route: BluetoothRoute) -> None:
        """Store the route used by the current connection attempt."""
        self.active_route = route

    @callback
    def async_select_route(self, source: str) -> None:
        """Set the route to use on the next connection."""
        self.selected_route_source = (
            None if source == AUTO_ROUTE_SOURCE else source
        )
        self._notify_listeners()

    async def async_reconnect_selected_route(self) -> None:
        """Reconnect the persistent session using the selected route."""
        try:
            async with self._operation_lock:
                self.available = False
                self.mech_status = None
                self.pending_locked = None
                self.active_route = None
                self._notify_listeners()
                await self.device.disconnect()
                await self._async_connect_locked()
        except asyncio.CancelledError:
            raise
        except Exception:
            self._handle_unexpected_disconnect(self.device)
            raise

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
    def _refresh_rssi_from_bluetooth_cache(self) -> bool:
        """Refresh RSSI from HA's latest cached connectable advertisement."""
        service_info = bluetooth.async_last_service_info(
            self.hass,
            self.address,
            connectable=True,
        )
        if service_info is None or service_info.rssi == self.rssi:
            return False
        self.rssi = service_info.rssi
        return True

    @callback
    def _handle_mech_status(
        self,
        _device: Sesame5,
        status: Sesame5MechStatus,
    ) -> None:
        """Store a mechanical-status publish from gomalock."""
        self.mech_status = status
        self.available = True
        self._refresh_rssi_from_bluetooth_cache()
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
        self.active_route = None
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
        self._refresh_rssi_from_bluetooth_cache()
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
        self._refresh_rssi_from_bluetooth_cache()
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
        started_at = monotonic()
        pending_was_set = False
        result: str | None = None
        try:
            async with self._operation_lock:
                if not self.device.is_logged_in:
                    await self._async_connect_locked()
                self.pending_locked = locked
                pending_was_set = True
                self._notify_listeners()
                if locked:
                    await self.device.lock("Home Assistant")
                else:
                    await self.device.unlock("Home Assistant")
        except asyncio.CancelledError:
            raise
        except Exception:
            result = "failed"
            if pending_was_set:
                self.available = False
                try:
                    await self.device.disconnect()
                finally:
                    self._handle_unexpected_disconnect(self.device)
            raise
        else:
            result = "success"
        finally:
            if pending_was_set:
                self.pending_locked = None
            if result is not None:
                self.last_operation_action = "lock" if locked else "unlock"
                self.last_operation_completed_at = datetime.now(UTC)
                self.last_operation_duration = round(monotonic() - started_at, 3)
                self.last_operation_result = result
            rssi_changed = self._refresh_rssi_from_bluetooth_cache()
            if pending_was_set or result is not None or rssi_changed:
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
        try:
            async with self._operation_lock:
                try:
                    await self.device.disconnect()
                except BleakError:
                    _LOGGER.debug(
                        "Ignoring Bluetooth disconnect error while stopping %s",
                        self.name,
                        exc_info=True,
                    )
        finally:
            self.available = False
            self.mech_status = None
            self.pending_locked = None
            self.active_route = None
            self._notify_listeners()
