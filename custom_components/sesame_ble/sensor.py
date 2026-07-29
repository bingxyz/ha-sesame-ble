"""Sensor platform for Sesame BLE."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from gomalock import Sesame5MechStatus
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTime,
)
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
    runtime = entry.runtime_data
    async_add_entities(
        [
            *(SesameSensor(runtime, description) for description in SENSORS),
            SesameSignalStrengthSensor(runtime),
            SesameBluetoothRouteSensor(runtime),
            SesameLastOperationResultSensor(runtime),
            SesameLastOperationDurationSensor(runtime),
        ]
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


class SesameSignalStrengthSensor(SesameEntity, SensorEntity):
    """Expose signal strength from the latest connectable advertisement."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "signal_strength"

    def __init__(self, runtime: SesameRuntime) -> None:
        """Initialize the signal-strength sensor."""
        super().__init__(runtime)
        self._attr_unique_id = f"{runtime.device_uuid}_signal_strength"

    @property
    def native_value(self) -> int | None:
        """Return RSSI from the latest connectable BLE advertisement."""
        return self.runtime.rssi


class SesameBluetoothRouteSensor(SesameEntity, SensorEntity):
    """Expose the Bluetooth scanner used by the active connection."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "bluetooth_route"

    def __init__(self, runtime: SesameRuntime) -> None:
        """Initialize the active Bluetooth route sensor."""
        super().__init__(runtime)
        self._attr_unique_id = f"{runtime.device_uuid}_bluetooth_route"

    @property
    def native_value(self) -> str | None:
        """Return the active scanner name."""
        route = self.runtime.active_route
        return route.name if route else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return source and route RSSI details."""
        route = self.runtime.active_route
        return {
            "source": route.source if route else None,
            "rssi": route.rssi if route else None,
            "selected_source": self.runtime.selected_route_source or "auto",
        }


class SesameLastOperationResultSensor(SesameEntity, SensorEntity):
    """Expose the result of the last Home Assistant lock operation."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_options: ClassVar[list[str]] = ["success", "failed"]
    _attr_translation_key = "last_operation_result"

    def __init__(self, runtime: SesameRuntime) -> None:
        """Initialize the last-operation-result sensor."""
        super().__init__(runtime)
        self._attr_unique_id = f"{runtime.device_uuid}_last_operation_result"

    @property
    def available(self) -> bool:
        """Keep a completed result visible after a connection failure."""
        return self.runtime.last_operation_result is not None

    @property
    def native_value(self) -> str | None:
        """Return whether the last Home Assistant operation succeeded."""
        return self.runtime.last_operation_result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return context for the last completed operation."""
        return {
            "action": self.runtime.last_operation_action,
            "completed_at": self.runtime.last_operation_completed_at,
            "duration_seconds": self.runtime.last_operation_duration,
        }


class SesameLastOperationDurationSensor(SesameEntity, SensorEntity):
    """Expose end-to-end duration of the last Home Assistant operation."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3
    _attr_translation_key = "last_operation_duration"

    def __init__(self, runtime: SesameRuntime) -> None:
        """Initialize the last-operation-duration sensor."""
        super().__init__(runtime)
        self._attr_unique_id = f"{runtime.device_uuid}_last_operation_duration"

    @property
    def available(self) -> bool:
        """Keep a completed duration visible after a connection failure."""
        return self.runtime.last_operation_duration is not None

    @property
    def native_value(self) -> float | None:
        """Return the last end-to-end operation duration in seconds."""
        return self.runtime.last_operation_duration
