"""Local Bluetooth support for CANDY HOUSE SESAME locks."""

from __future__ import annotations

import logging

from gomalock import SesameConnectionError, SesameLoginError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DEVICE_UUID, CONF_SECRET_KEY, PLATFORMS
from .runtime import SesameRuntime

_LOGGER = logging.getLogger(__name__)

type SesameConfigEntry = ConfigEntry[SesameRuntime]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SesameConfigEntry,
) -> bool:
    """Set up one discovered Sesame lock."""
    runtime = SesameRuntime(
        hass,
        address=entry.data[CONF_ADDRESS],
        device_uuid=entry.data[CONF_DEVICE_UUID],
        secret_key=entry.data[CONF_SECRET_KEY],
        name=entry.title,
    )
    entry.runtime_data = runtime
    try:
        await runtime.async_start()
    except (SesameConnectionError, SesameLoginError, TimeoutError) as err:
        await runtime.async_stop()
        raise ConfigEntryNotReady(
            f"Unable to connect to {entry.title} through Bluetooth"
        ) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SesameConfigEntry,
) -> bool:
    """Unload entities and close the persistent BLE connection."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    return True
