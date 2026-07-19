"""Shared entity implementation for Sesame BLE."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MODEL_NAME
from .runtime import SesameRuntime


class SesameEntity(Entity):
    """Base entity backed by a Sesame runtime."""

    _attr_has_entity_name = True

    def __init__(self, runtime: SesameRuntime) -> None:
        """Initialize common device metadata."""
        self.runtime = runtime
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.device_uuid)},
            connections={(CONNECTION_BLUETOOTH, runtime.address)},
            manufacturer="CANDY HOUSE",
            model=MODEL_NAME,
            name=runtime.name,
            serial_number=runtime.device_uuid,
        )

    @property
    def available(self) -> bool:
        """Return whether the authenticated BLE session is available."""
        return self.runtime.available

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime state changes."""
        self.async_on_remove(
            self.runtime.async_add_listener(self._async_write_runtime_state)
        )

    def _async_write_runtime_state(self) -> None:
        """Write cached runtime state to Home Assistant."""
        self.async_write_ha_state()
