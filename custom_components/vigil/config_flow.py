"""Config and options flow for Vigil."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    ARM_MODES,
    CONF_APPROACH_ALL,
    CONF_APPROACH_SENSORS,
    CONF_CAMERA,
    CONF_CODE,
    CONF_CODE_ARM_REQUIRED,
    CONF_COLOUR_LIGHTS,
    CONF_ENTRY_DELAY,
    CONF_EXCLUDED,
    CONF_EXIT_DELAY,
    CONF_FLASH_LIGHTS,
    CONF_INTRUDER_MESSAGE,
    CONF_MONITOR_ALL,
    CONF_MONITORED_SENSORS,
    CONF_NOTIFY_TARGETS,
    CONF_PRESENCE_ENTITIES,
    CONF_SPEAKERS,
    CONF_TTS_ENGINE,
    CONF_TTS_VOICE,
    DEFAULT_ENTRY_DELAY,
    DEFAULT_EXIT_DELAY,
    DEFAULT_INTRUDER_MESSAGE,
    DEFAULT_TTS_ENGINE,
    DOMAIN,
    MODE_LABELS,
)
from .discovery import discover_motion_sensors, discover_person_sensors


def _core_schema(d: dict[str, Any]) -> vol.Schema:
    """Core settings: code, delays, TTS, intruder message."""
    return vol.Schema(
        {
            vol.Optional(CONF_CODE, default=d.get(CONF_CODE, "")): selector.TextSelector(
                selector.TextSelectorConfig(type="password")
            ),
            vol.Optional(
                CONF_CODE_ARM_REQUIRED, default=d.get(CONF_CODE_ARM_REQUIRED, False)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_EXIT_DELAY, default=d.get(CONF_EXIT_DELAY, DEFAULT_EXIT_DELAY)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=300, step=5, unit_of_measurement="seconds", mode="box"
                )
            ),
            vol.Optional(
                CONF_ENTRY_DELAY, default=d.get(CONF_ENTRY_DELAY, DEFAULT_ENTRY_DELAY)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=300, step=5, unit_of_measurement="seconds", mode="box"
                )
            ),
            vol.Optional(
                CONF_TTS_ENGINE,
                description={
                    "suggested_value": d.get(CONF_TTS_ENGINE, DEFAULT_TTS_ENGINE)
                },
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="tts")
            ),
            vol.Optional(
                CONF_TTS_VOICE, default=d.get(CONF_TTS_VOICE, "")
            ): selector.TextSelector(),
            vol.Optional(
                CONF_INTRUDER_MESSAGE,
                default=d.get(CONF_INTRUDER_MESSAGE, DEFAULT_INTRUDER_MESSAGE),
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
        }
    )


def _sensors_schema(hass, d: dict[str, Any]) -> vol.Schema:
    """'Monitor all' toggles (default on) + explicit lists + per-mode exclusions.

    With the toggles on, no sensor picking is needed at all. The explicit lists
    are pre-filled with everything detected, so even if you turn a toggle off
    you start from "all selected" and just remove what you don't want.
    """
    fields: dict = {
        vol.Optional(
            CONF_MONITOR_ALL, default=d.get(CONF_MONITOR_ALL, True)
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_MONITORED_SENSORS,
            default=d.get(CONF_MONITORED_SENSORS) or discover_motion_sensors(hass),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
        ),
        vol.Optional(
            CONF_APPROACH_ALL, default=d.get(CONF_APPROACH_ALL, True)
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_APPROACH_SENSORS,
            default=d.get(CONF_APPROACH_SENSORS) or discover_person_sensors(hass),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
        ),
    }
    for mode in ARM_MODES:
        key = f"{CONF_EXCLUDED}_{mode}"
        fields[
            vol.Optional(key, default=d.get(key, []))
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
        )
    return vol.Schema(fields)


def _response_schema(hass, d: dict[str, Any]) -> vol.Schema:
    """Lights, speakers, presence, notify targets, camera."""
    notify_services = sorted(hass.services.async_services().get("notify", {}).keys())
    notify_options = [
        selector.SelectOptionDict(value=f"notify.{name}", label=name)
        for name in notify_services
    ]
    return vol.Schema(
        {
            vol.Optional(
                CONF_COLOUR_LIGHTS, default=d.get(CONF_COLOUR_LIGHTS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="light", multiple=True)
            ),
            vol.Optional(
                CONF_FLASH_LIGHTS, default=d.get(CONF_FLASH_LIGHTS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="light", multiple=True)
            ),
            vol.Optional(
                CONF_SPEAKERS, default=d.get(CONF_SPEAKERS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player", multiple=True)
            ),
            vol.Optional(
                CONF_PRESENCE_ENTITIES, default=d.get(CONF_PRESENCE_ENTITIES, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["person", "device_tracker"], multiple=True
                )
            ),
            vol.Optional(
                CONF_NOTIFY_TARGETS, default=d.get(CONF_NOTIFY_TARGETS, [])
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=notify_options, multiple=True, custom_value=True
                )
            ),
            vol.Optional(
                CONF_CAMERA,
                description={"suggested_value": d.get(CONF_CAMERA) or None},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="camera")
            ),
        }
    )


class VigilConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id="user", data_schema=_core_schema({})
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_response()
        return self.async_show_form(
            step_id="sensors", data_schema=_sensors_schema(self.hass, {})
        )

    async def async_step_response(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="Vigil", data=self._data)
        return self.async_show_form(
            step_id="response", data_schema=_response_schema(self.hass, {})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VigilOptionsFlow()


class VigilOptionsFlow(OptionsFlow):
    """Reconfigure structural settings after setup."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def _merged(self) -> dict[str, Any]:
        merged = dict(self.config_entry.data)
        merged.update(self.config_entry.options)
        merged.update(self._data)
        return merged

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id="init", data_schema=_core_schema(self._merged())
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_response()
        return self.async_show_form(
            step_id="sensors", data_schema=_sensors_schema(self.hass, self._merged())
        )

    async def async_step_response(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)
        return self.async_show_form(
            step_id="response",
            data_schema=_response_schema(self.hass, self._merged()),
        )
