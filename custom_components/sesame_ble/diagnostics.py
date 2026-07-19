"""Diagnostics for Sesame BLE."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SesameConfigEntry
from .const import CONF_SECRET_KEY


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant,
    entry: SesameConfigEntry,
) -> dict[str, Any]:
    """Return redacted config and non-sensitive runtime state."""
    runtime = entry.runtime_data
    status = runtime.mech_status
    return {
        "config_entry": async_redact_data(dict(entry.data), {CONF_SECRET_KEY}),
        "runtime": {
            "available": runtime.available,
            "address": runtime.address,
            "device_uuid": runtime.device_uuid,
            "connected": runtime.device.is_connected,
            "logged_in": runtime.device.is_logged_in,
            "position": status.position if status else None,
            "target": status.target if status else None,
            "battery_voltage": status.battery_voltage if status else None,
            "battery_percentage": status.battery_percentage if status else None,
        },
    }
