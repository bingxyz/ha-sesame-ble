"""Lock platform for Sesame BLE."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SesameEntity
from .runtime import SesameRuntime


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry[SesameRuntime],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sesame lock entity."""
    async_add_entities([SesameLockEntity(entry.runtime_data)])


class SesameLockEntity(SesameEntity, LockEntity):
    """Control and display a SESAME 5 Pro lock."""

    _attr_name = None

    def __init__(self, runtime: SesameRuntime) -> None:
        """Initialize the primary lock entity."""
        super().__init__(runtime)
        self._attr_unique_id = runtime.device_uuid

    @property
    def is_locked(self) -> bool | None:
        """Return the calibrated lock-range state."""
        status = self.runtime.mech_status
        if status is None:
            return None
        if status.is_in_lock_range:
            return True
        if status.is_in_unlock_range:
            return False
        return None

    @property
    def is_locking(self) -> bool:
        """Return whether an explicit HA lock command is pending."""
        return self.runtime.pending_locked is True

    @property
    def is_unlocking(self) -> bool:
        """Return whether an explicit HA unlock command is pending."""
        return self.runtime.pending_locked is False

    @property
    def is_jammed(self) -> bool:
        """Return whether Sesame reports a critical or clutch failure."""
        status = self.runtime.mech_status
        return bool(status and (status.is_clutch_failed or status.is_critical))

    async def async_lock(self, **_kwargs: Any) -> None:
        """Lock the Sesame."""
        try:
            await self.runtime.async_set_locked(locked=True)
        except Exception as err:
            raise HomeAssistantError(
                translation_domain="sesame_ble",
                translation_key="lock_failed",
            ) from err

    async def async_unlock(self, **_kwargs: Any) -> None:
        """Unlock the Sesame."""
        try:
            await self.runtime.async_set_locked(locked=False)
        except Exception as err:
            raise HomeAssistantError(
                translation_domain="sesame_ble",
                translation_key="unlock_failed",
            ) from err
