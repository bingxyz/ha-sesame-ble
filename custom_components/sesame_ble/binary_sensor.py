"""Binary sensor platform for Sesame BLE."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SesameEntity
from .runtime import SesameRuntime


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry[SesameRuntime],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the low-battery binary sensor."""
    async_add_entities([SesameLowBatterySensor(entry.runtime_data)])


class SesameLowBatterySensor(SesameEntity, BinarySensorEntity):
    """Expose Sesame's own critical-battery flag."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "battery_low"

    def __init__(self, runtime: SesameRuntime) -> None:
        """Initialize the low-battery sensor."""
        super().__init__(runtime)
        self._attr_unique_id = f"{runtime.device_uuid}_battery_low"

    @property
    def is_on(self) -> bool | None:
        """Return the latest battery-critical flag."""
        status = self.runtime.mech_status
        if status is None:
            return None
        return status.is_battery_critical
