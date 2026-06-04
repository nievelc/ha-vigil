"""Vigil binary sensor: the tier-1 'alerting' state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VigilConfigEntry
from .entity import VigilEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VigilConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vigil alerting binary sensor."""
    async_add_entities([VigilAlertingBinarySensor(entry.runtime_data.coordinator)])


class VigilAlertingBinarySensor(VigilEntity, BinarySensorEntity):
    """On while the notify tier is active (a heads-up, below full alarm)."""

    _attr_name = "Alerting"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:bell-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_alerting"

    @property
    def is_on(self) -> bool:
        return self.coordinator.alerting
