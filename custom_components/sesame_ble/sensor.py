"""Sensor platform for Sesame BLE."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from gomalock import Sesame5MechStatus
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, PERCENTAGE, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ANGLE_SCALE
from .entity import SesameEntity
from .runtime import SesameRuntime


@dataclass(frozen=True, kw_only=True)
class SesameSensorDescription(SensorEntityDescription):
    """Describe a Sesame mechanical-status sensor."""

    value_fn: Callable[[Sesame5MechStatus], float | int]


SENSORS = (
    SesameSensorDescription(
        key="angle",
        translation_key="angle",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        suggested_display_precision=1,
        value_fn=lambda status: round(status.position * ANGLE_SCALE, 1),
    ),
    SesameSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.battery_percentage,
    ),
    SesameSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.battery_voltage,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry[SesameRuntime],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sesame sensors."""
    async_add_entities(
        SesameSensor(entry.runtime_data, description) for description in SENSORS
    )


class SesameSensor(SesameEntity, SensorEntity):
    """Expose cached mechanical status as a sensor."""

    entity_description: SesameSensorDescription

    def __init__(
        self,
        runtime: SesameRuntime,
        description: SesameSensorDescription,
    ) -> None:
        """Initialize one sensor."""
        super().__init__(runtime)
        self.entity_description = description
        self._attr_unique_id = f"{runtime.device_uuid}_{description.key}"

    @property
    def native_value(self) -> float | int | None:
        """Return a value from the latest mechanical status."""
        status = self.runtime.mech_status
        if status is None:
            return None
        return self.entity_description.value_fn(status)
