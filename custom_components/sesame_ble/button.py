"""Bluetooth route controls for Sesame BLE."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SesameEntity
from .runtime import SesameRuntime


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry[SesameRuntime],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bluetooth route button."""
    async_add_entities([SesameBluetoothRouteReconnectButton(entry.runtime_data)])


class SesameBluetoothRouteReconnectButton(SesameEntity, ButtonEntity):
    """Reconnect the persistent session using the selected route."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "bluetooth_route_reconnect"

    def __init__(self, runtime: SesameRuntime) -> None:
        """Initialize the route reconnect button."""
        super().__init__(runtime)
        self._attr_unique_id = f"{runtime.device_uuid}_bluetooth_route_reconnect"

    @property
    def available(self) -> bool:
        """Keep manual reconnect available while the SESAME is disconnected."""
        return True

    async def async_press(self) -> None:
        """Reconnect using the selected Bluetooth route."""
        await self.runtime.async_reconnect_selected_route()
