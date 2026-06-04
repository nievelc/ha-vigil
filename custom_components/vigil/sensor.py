"""Vigil sensors: the confidence score and diagnostics."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VigilConfigEntry
from .entity import VigilEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VigilConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vigil sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            VigilConfidenceSensor(coordinator),
            VigilActiveCountSensor(coordinator),
        ]
    )


class VigilConfidenceSensor(VigilEntity, SensorEntity):
    """The 0-100 intruder-confidence score."""

    _attr_name = "Confidence"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:shield-search"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_confidence"

    @property
    def native_value(self) -> int:
        return round(self.coordinator.score)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "tier": self.coordinator.tier,
            "armed_mode": self.coordinator.armed_mode,
            "last_trip": self.coordinator.last_trip_name,
        }


class VigilActiveCountSensor(VigilEntity, SensorEntity):
    """How many monitored sensors are active right now (diagnostic)."""

    _attr_name = "Active sensors"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_active_count"

    @property
    def native_value(self) -> int:
        return len(self.coordinator._active_sensors)
