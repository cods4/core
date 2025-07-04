"""Config flow for NZ WITS Spot Price integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import CannotConnect, InvalidAuth, WitsApiClient
from .const import DOMAIN, NODE_OPTIONS

_LOGGER = logging.getLogger(__name__)

CONF_NODE = "node"


class NzWitsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NZ WITS Spot Price."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> NzWitsOptionsFlowHandler:
        """Create the options flow."""
        return NzWitsOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_credentials(
                    user_input[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                    user_input[CONF_NODE],
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_NODE])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"NZ WITS ({user_input[CONF_NODE]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_NODE, default="TGA0331"): SelectSelector(
                        SelectSelectorConfig(
                            options=NODE_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_credentials(
                    user_input[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                    user_input[CONF_NODE],
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                assert self.reauth_entry is not None
                return self.async_update_reload_and_abort(
                    self.reauth_entry,
                    data_updates=user_input,
                )

        assert self.reauth_entry is not None
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CLIENT_ID,
                        default=self.reauth_entry.data[CONF_CLIENT_ID],
                    ): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(
                        CONF_NODE,
                        default=self.reauth_entry.data[CONF_NODE],
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=NODE_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(
        self, client_id: str, client_secret: str, node: str
    ) -> None:
        """Test the credentials."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        api = WitsApiClient(client_id, client_secret, node, session)
        await api.test_authentication()


class NzWitsOptionsFlowHandler(OptionsFlow):
    """Handle NZ WITS options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "update_rtd",
                        default=self.config_entry.options.get("update_rtd", True),
                    ): bool,
                    vol.Optional(
                        "update_interim",
                        default=self.config_entry.options.get("update_interim", True),
                    ): bool,
                    vol.Optional(
                        "update_prss",
                        default=self.config_entry.options.get("update_prss", True),
                    ): bool,
                    vol.Optional(
                        "update_prsl",
                        default=self.config_entry.options.get("update_prsl", True),
                    ): bool,
                }
            ),
        )