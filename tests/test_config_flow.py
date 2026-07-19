"""Tests for Sesame BLE discovery and setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_BLUETOOTH
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from custom_components.sesame_ble import config_flow as config_flow_module
from custom_components.sesame_ble.config_flow import SesameBleConfigFlow
from custom_components.sesame_ble.const import (
    CONF_DEVICE_UUID,
    CONF_SECRET_KEY,
    CONF_SHARE_URL,
    DOMAIN,
)

from .helpers import TEST_ADDRESS, TEST_SECRET, TEST_UUID, make_service_info


def _mock_flow_integration(hass: HomeAssistant) -> None:
    """Register a dependency-free integration while exercising the real flow."""
    mock_integration(
        hass,
        MockModule(DOMAIN, partial_manifest={"config_flow": True}),
    )
    mock_platform(hass, f"{DOMAIN}.config_flow", config_flow_module)


async def test_bluetooth_discovery_and_manual_secret(hass: HomeAssistant) -> None:
    """Discover, validate and create an entry with a manual secret."""
    _mock_flow_integration(hass)
    service_info = make_service_info()
    with mock_config_flow(DOMAIN, SesameBleConfigFlow):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info,
        )

        assert result["type"] == "form"
        assert result["step_id"] == "credentials"

        with patch(
            "custom_components.sesame_ble.config_flow.async_validate_connection",
            new=AsyncMock(),
        ) as validate:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_NAME: "Entrance",
                    CONF_SHARE_URL: "",
                    CONF_SECRET_KEY: TEST_SECRET,
                },
            )

    assert result["type"] == "create_entry"
    assert result["title"] == "Entrance"
    assert result["data"] == {
        CONF_ADDRESS: TEST_ADDRESS,
        CONF_DEVICE_UUID: str(TEST_UUID),
        CONF_SECRET_KEY: TEST_SECRET,
    }
    validate.assert_awaited_once_with(
        hass,
        address=TEST_ADDRESS,
        secret_key=TEST_SECRET,
    )


async def test_bluetooth_filters_other_sesame_models(hass: HomeAssistant) -> None:
    """Abort discovery for a non-Pro model in the first release."""
    _mock_flow_integration(hass)
    with mock_config_flow(DOMAIN, SesameBleConfigFlow):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=make_service_info(model=5),
        )

    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"


async def test_credentials_require_exactly_one_source(hass: HomeAssistant) -> None:
    """Reject empty credentials before attempting a BLE connection."""
    _mock_flow_integration(hass)
    with mock_config_flow(DOMAIN, SesameBleConfigFlow):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=make_service_info(),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Entrance",
                CONF_SHARE_URL: "",
                CONF_SECRET_KEY: "",
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "provide_one_credential"}
