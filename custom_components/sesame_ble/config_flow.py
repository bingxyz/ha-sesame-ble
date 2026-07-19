"""Config flow for Sesame BLE."""

from __future__ import annotations

import logging
from typing import Any, override

import voluptuous as vol
from gomalock import SesameConnectionError, SesameLoginError, SesameOperationError
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers import selector

from .bluetooth import async_validate_connection, parse_sesame_advertisement
from .const import (
    CONF_DEVICE_UUID,
    CONF_SECRET_KEY,
    CONF_SHARE_URL,
    DOMAIN,
    MODEL_NAME,
)
from .credentials import (
    SesameCredentials,
    credentials_from_share_url,
    normalize_secret_key,
)
from .exceptions import (
    DeviceMismatchError,
    InvalidCredentialsError,
    UnsupportedDeviceError,
)

_LOGGER = logging.getLogger(__name__)


class SesameBleConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a Sesame BLE config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize discovery state."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._device_uuid: str | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def _async_set_discovery(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> bool:
        """Validate and retain one Bluetooth discovery."""
        advertisement = parse_sesame_advertisement(discovery_info)
        if advertisement is None or not discovery_info.connectable:
            return False

        device_uuid = str(advertisement.device_uuid)
        await self.async_set_unique_id(device_uuid)
        self._abort_if_unique_id_configured(
            updates={CONF_ADDRESS: discovery_info.address}
        )
        self._discovery_info = discovery_info
        self._device_uuid = device_uuid
        self.context["title_placeholders"] = {
            "name": MODEL_NAME,
            "identifier": device_uuid[-4:].upper(),
        }
        return True

    @override
    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> ConfigFlowResult:
        """Handle automatic Bluetooth discovery."""
        if not await self._async_set_discovery(discovery_info):
            return self.async_abort(reason="not_supported")
        return await self.async_step_credentials()

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Find a device when the integration is added manually."""
        if user_input is not None:
            discovery_info = self._discovered_devices[user_input[CONF_ADDRESS]]
            if not await self._async_set_discovery(discovery_info):
                return self.async_abort(reason="not_supported")
            return await self.async_step_credentials()

        await bluetooth.async_request_active_scan(self.hass)
        configured_ids = self._async_current_ids(include_ignore=False)
        self._discovered_devices = {}
        for service_info in bluetooth.async_discovered_service_info(
            self.hass,
            connectable=True,
        ):
            advertisement = parse_sesame_advertisement(service_info)
            if (
                advertisement is None
                or str(advertisement.device_uuid) in configured_ids
            ):
                continue
            self._discovered_devices[service_info.address] = service_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")
        if len(self._discovered_devices) == 1:
            discovery_info = next(iter(self._discovered_devices.values()))
            await self._async_set_discovery(discovery_info)
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: self._discovery_name(info)
                            for address, info in self._discovered_devices.items()
                        }
                    )
                }
            ),
        )

    def _discovery_name(self, service_info: BluetoothServiceInfoBleak) -> str:
        """Build a human-readable discovery name."""
        advertisement = parse_sesame_advertisement(service_info)
        if advertisement is None:
            return MODEL_NAME
        return f"{MODEL_NAME} {str(advertisement.device_uuid)[-4:].upper()}"

    async def async_step_credentials(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Collect a manager/owner share URL or a manual secret key."""
        assert self._discovery_info is not None
        assert self._device_uuid is not None

        errors: dict[str, str] = {}
        if user_input is not None:
            share_url = str(user_input.get(CONF_SHARE_URL, "")).strip()
            manual_secret = str(user_input.get(CONF_SECRET_KEY, "")).strip()
            if bool(share_url) == bool(manual_secret):
                errors["base"] = "provide_one_credential"
            else:
                try:
                    if share_url:
                        credentials = credentials_from_share_url(
                            share_url,
                            expected_uuid=self._device_uuid,
                        )
                    else:
                        credentials = SesameCredentials(
                            device_name=MODEL_NAME,
                            device_uuid=self._device_uuid,
                            secret_key=normalize_secret_key(manual_secret),
                        )
                    await async_validate_connection(
                        self.hass,
                        address=self._discovery_info.address,
                        secret_key=credentials.secret_key,
                    )
                except InvalidCredentialsError:
                    errors["base"] = "invalid_credentials"
                except DeviceMismatchError:
                    errors["base"] = "device_mismatch"
                except UnsupportedDeviceError:
                    errors["base"] = "not_supported"
                except SesameLoginError:
                    errors["base"] = "invalid_auth"
                except SesameConnectionError, TimeoutError:
                    errors["base"] = "cannot_connect"
                except SesameOperationError:
                    errors["base"] = "invalid_auth"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error while validating Sesame credentials"
                    )
                    errors["base"] = "unknown"
                else:
                    requested_name = str(user_input.get(CONF_NAME, "")).strip()
                    title = requested_name or credentials.device_name
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_ADDRESS: self._discovery_info.address,
                            CONF_DEVICE_UUID: credentials.device_uuid,
                            CONF_SECRET_KEY: credentials.secret_key,
                        },
                    )

        suggested_name = f"{MODEL_NAME} {self._device_uuid[-4:].upper()}"
        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=suggested_name): str,
                    vol.Optional(CONF_SHARE_URL, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        )
                    ),
                    vol.Optional(CONF_SECRET_KEY, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "name": suggested_name,
                "uuid": self._device_uuid,
            },
        )
