"""Vigil switches: channel enables, test mode, and per-speaker toggles."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VigilConfigEntry
from .const import (
    CONF_INTERNAL_ALARM_ENABLED,
    CONF_MOBILE_NOTIFY_ENABLED,
    CONF_SPEAKER_ENABLED,
    CONF_SPEAKERS,
    CONF_TEST_MODE,
)
from .entity import VigilEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VigilConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vigil switches."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SwitchEntity] = [
        VigilSwitch(coordinator, CONF_MOBILE_NOTIFY_ENABLED,
                    "Mobile notifications", True, "mdi:cellphone-message"),
        VigilSwitch(coordinator, CONF_INTERNAL_ALARM_ENABLED,
                    "Internal alarm (speakers/lights)", True, "mdi:bullhorn"),
        VigilSwitch(coordinator, CONF_TEST_MODE,
                    "Test mode", False, "mdi:test-tube"),
    ]

    for entity_id in coordinator.get_config(CONF_SPEAKERS, []) or []:
        state = hass.states.get(entity_id)
        label = state.name if state else entity_id
        entities.append(
            VigilSwitch(
                coordinator,
                f"{CONF_SPEAKER_ENABLED}_{entity_id}",
                f"Speaker: {label}",
                True,
                "mdi:speaker",
            )
        )

    async_add_entities(entities)


class VigilSwitch(VigilEntity, SwitchEntity):
    """A live boolean tunable backed by the coordinator's store."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator, key: str, name: str, default: bool, icon: str
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._default = default
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.get_tunable(self._key, self._default))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_tunable(self._key, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_tunable(self._key, False)
