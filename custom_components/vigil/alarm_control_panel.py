"""Vigil alarm_control_panel entity — the arm/disarm state machine face."""

from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VigilConfigEntry
from .const import (
    CONF_CODE,
    CONF_CODE_ARM_REQUIRED,
    MODE_AWAY,
    MODE_HOME,
    MODE_NIGHT,
    MODE_VACATION,
    TIER_NONE,
)
from .entity import VigilEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VigilConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vigil alarm panel."""
    async_add_entities([VigilAlarmPanel(entry.runtime_data.coordinator)])


class VigilAlarmPanel(VigilEntity, AlarmControlPanelEntity):
    """The Vigil alarm control panel."""

    _attr_name = None  # use the device name
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_VACATION
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_panel"

    @property
    def _code(self) -> str | None:
        code = self.coordinator.get_config(CONF_CODE)
        return code or None

    @property
    def code_format(self) -> CodeFormat | None:
        if not self._code:
            return None
        return CodeFormat.NUMBER if self._code.isdigit() else CodeFormat.TEXT

    @property
    def code_arm_required(self) -> bool:
        return bool(self.coordinator.get_config(CONF_CODE_ARM_REQUIRED, False))

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        return self.coordinator.alarm_state

    @property
    def extra_state_attributes(self) -> dict:
        coord = self.coordinator
        monitored = coord._master_sensors()
        approach = coord.approach_sensors()
        return {
            "confidence": round(coord.score),
            "tier": coord.tier,
            "armed_mode": coord.armed_mode,
            "sounding": coord.sounding,
            "test_mode": coord.test_mode,
            "last_trip": coord.last_trip_name,
            "monitored_sensor_count": len(monitored),
            "monitored_sensors": monitored,
            "approach_sensors": approach,
        }

    # ------------------------------------------------------------------
    def _check(self, code: str | None) -> bool:
        if not self._code:
            return True
        return code == self._code

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        if self._code and not self._check(code):
            return
        await self.coordinator.async_disarm()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        if self.code_arm_required and not self._check(code):
            return
        await self.coordinator.async_arm(MODE_AWAY)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        if self.code_arm_required and not self._check(code):
            return
        await self.coordinator.async_arm(MODE_HOME)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        if self.code_arm_required and not self._check(code):
            return
        await self.coordinator.async_arm(MODE_NIGHT)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        if self.code_arm_required and not self._check(code):
            return
        await self.coordinator.async_arm(MODE_VACATION)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        await self.coordinator.async_trigger()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
