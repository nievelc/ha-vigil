"""Shared base entity for Vigil."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VigilCoordinator


class VigilEntity(CoordinatorEntity[VigilCoordinator]):
    """Base entity that binds all Vigil entities to one device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VigilCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="Vigil",
            manufacturer="Vigil",
            model="Confidence Alarm",
        )
