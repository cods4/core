"""Config flow for NZ WITS Spot Price integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import CannotConnect, InvalidAuth, WitsApiClient
from .const import (
    CONF_NODE,
    CONF_UPDATE_INTERIM,
    CONF_UPDATE_PRSL,
    CONF_UPDATE_PRSS,
    CONF_UPDATE_RTD,
    DOMAIN,
    NODE_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


class NzWitsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NZ WITS Spot Price."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.reauth_entry: ConfigEntry | None = None
        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._selected_node: str | None = None
        self._available_schedules: list[dict[str, Any]] = []

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
        """Handle the initial step - collect credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_credentials(
                    user_input[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                )
                self._client_id = user_input[CONF_CLIENT_ID]
                self._client_secret = user_input[CONF_CLIENT_SECRET]
                return await self.async_step_node()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
        )

    async def async_step_node(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle node selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store selected node and proceed to schedule selection
            selected_node = user_input[CONF_NODE]
            await self.async_set_unique_id(selected_node)
            self._abort_if_unique_id_configured()
            self._selected_node = selected_node
            return await self.async_step_schedules()

        # Use all validated nodes - these have been tested and confirmed to work with the WITS API
        default_node = NODE_OPTIONS[0] if NODE_OPTIONS else "BEN2201"

        return self.async_show_form(
            step_id="node",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NODE, default=default_node): SelectSelector(
                        SelectSelectorConfig(
                            options=NODE_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_schedules(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle schedule selection step."""
        if user_input is not None:
            # This is schedule selection - use stored node
            final_data = {
                CONF_CLIENT_ID: self._client_id,
                CONF_CLIENT_SECRET: self._client_secret,
                CONF_NODE: self._selected_node,
                CONF_UPDATE_RTD: user_input.get(CONF_UPDATE_RTD, True),
                CONF_UPDATE_INTERIM: user_input.get(CONF_UPDATE_INTERIM, True),
                CONF_UPDATE_PRSS: user_input.get(CONF_UPDATE_PRSS, True),
                CONF_UPDATE_PRSL: user_input.get(CONF_UPDATE_PRSL, True),
            }
            return self.async_create_entry(
                title=f"NZ WITS ({self._selected_node})",
                data=final_data,
            )

        # Fetch available schedules from API
        if not self._available_schedules:
            try:
                session = aiohttp_client.async_get_clientsession(self.hass)
                # Ensure client_id and client_secret are strings
                if self._client_id and self._client_secret and self._selected_node:
                    api = WitsApiClient(
                        self._client_id,
                        self._client_secret,
                        self._selected_node,
                        session,
                    )
                    self._available_schedules = await api.get_available_schedules()
            except Exception:
                _LOGGER.exception("Failed to fetch schedules from API")
                self._available_schedules = []

        return self.async_show_form(
            step_id="schedules",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_UPDATE_RTD, default=True): bool,
                    vol.Optional(CONF_UPDATE_INTERIM, default=True): bool,
                    vol.Optional(CONF_UPDATE_PRSS, default=True): bool,
                    vol.Optional(CONF_UPDATE_PRSL, default=True): bool,
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
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
        self, client_id: str, client_secret: str, node: str = "BEN2201"
    ) -> None:
        """Test the credentials."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        api = WitsApiClient(client_id, client_secret, node, session)
        await api.test_authentication()


class NzWitsOptionsFlowHandler(OptionsFlow):
    """Handle NZ WITS options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # If node was changed, update the config entry data as well
            updated_data = dict(self.config_entry.data)
            if CONF_NODE in user_input:
                updated_data[CONF_NODE] = user_input[CONF_NODE]

            # Update config entry with new node if changed
            if updated_data != self.config_entry.data:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=updated_data
                )

            # Remove node from options data
            options_data = {k: v for k, v in user_input.items() if k not in [CONF_NODE]}
            return self.async_create_entry(title="", data=options_data)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NODE,
                        default=self.config_entry.data.get(CONF_NODE, "BEN2201"),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=NODE_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_UPDATE_RTD,
                        default=self.config_entry.options.get(CONF_UPDATE_RTD, True),
                    ): bool,
                    vol.Optional(
                        CONF_UPDATE_INTERIM,
                        default=self.config_entry.options.get(
                            CONF_UPDATE_INTERIM, True
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_UPDATE_PRSS,
                        default=self.config_entry.options.get(CONF_UPDATE_PRSS, True),
                    ): bool,
                    vol.Optional(
                        CONF_UPDATE_PRSL,
                        default=self.config_entry.options.get(CONF_UPDATE_PRSL, True),
                    ): bool,
                }
            ),
        )
