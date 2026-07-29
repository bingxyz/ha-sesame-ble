"""Bluetooth route selection for Sesame BLE."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
    """Set up the Bluetooth route selector."""
    async_add_entities([SesameBluetoothRouteSelect(entry.runtime_data)])


class SesameBluetoothRouteSelect(SesameEntity, SelectEntity):
    """Choose the Bluetooth route for the next persistent connection."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "bluetooth_route"

    def __init__(self, runtime: SesameRuntime) -> None:
        """Initialize the route selector."""
        super().__init__(runtime)
        self._attr_unique_id = f"{runtime.device_uuid}_bluetooth_route_select"

    @property
    def available(self) -> bool:
        """Keep route selection available while the SESAME is disconnected."""
        return True

    @property
    def options(self) -> list[str]:
        """Return automatic and currently discovered route sources."""
        return self.runtime.route_options

    @property
    def current_option(self) -> str:
        """Return the selected route option."""
        return self.runtime.selected_route_option

    async def async_select_option(self, option: str) -> None:
        """Set the route used by the next manual reconnect."""
        self.runtime.select_route_option(option)
