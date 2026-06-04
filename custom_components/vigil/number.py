"""Vigil live-tunable number entities (cutpoints, weights, timings)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VigilConfigEntry
from .const import (
    ARM_MODES,
    CONF_ALARM_CUTPOINT,
    CONF_ANNOUNCE_VOLUME,
    CONF_APPROACH_BOOST,
    CONF_APPROACH_WINDOW_S,
    CONF_CONCURRENCY_WEIGHT,
    CONF_DECAY_WINDOW_MIN,
    CONF_NOTIFY_CUTPOINT,
    CONF_REALERT_COOLDOWN,
    CONF_TRIP_WEIGHT,
    DEFAULT_ANNOUNCE_VOLUME,
    DEFAULT_APPROACH_BOOST,
    DEFAULT_APPROACH_WINDOW_S,
    DEFAULT_CONCURRENCY_WEIGHT,
    DEFAULT_CUTPOINTS,
    DEFAULT_DECAY_WINDOW_MIN,
    DEFAULT_REALERT_COOLDOWN,
    DEFAULT_TRIP_WEIGHT,
    MODE_LABELS,
)
from .entity import VigilEntity


@dataclass(frozen=True)
class VigilNumberDesc:
    """Describes one tunable number."""

    key: str
    name: str
    default: float
    min_value: float
    max_value: float
    step: float
    unit: str | None = None
    icon: str | None = None


def _build_descriptors() -> list[VigilNumberDesc]:
    descs: list[VigilNumberDesc] = []
    for mode in ARM_MODES:
        label = MODE_LABELS[mode]
        descs.append(
            VigilNumberDesc(
                key=f"{CONF_NOTIFY_CUTPOINT}_{mode}",
                name=f"{label} notify cutpoint",
                default=DEFAULT_CUTPOINTS[mode][CONF_NOTIFY_CUTPOINT],
                min_value=0,
                max_value=100,
                step=1,
                unit=PERCENTAGE,
                icon="mdi:bell-ring-outline",
            )
        )
        descs.append(
            VigilNumberDesc(
                key=f"{CONF_ALARM_CUTPOINT}_{mode}",
                name=f"{label} alarm cutpoint",
                default=DEFAULT_CUTPOINTS[mode][CONF_ALARM_CUTPOINT],
                min_value=0,
                max_value=100,
                step=1,
                unit=PERCENTAGE,
                icon="mdi:bullhorn",
            )
        )
    descs.extend(
        [
            VigilNumberDesc(
                key=CONF_DECAY_WINDOW_MIN,
                name="Decay window",
                default=DEFAULT_DECAY_WINDOW_MIN,
                min_value=0.5,
                max_value=60,
                step=0.5,
                unit=UnitOfTime.MINUTES,
                icon="mdi:timer-sand",
            ),
            VigilNumberDesc(
                key=CONF_ANNOUNCE_VOLUME,
                name="Announce volume",
                default=DEFAULT_ANNOUNCE_VOLUME,
                min_value=0,
                max_value=1,
                step=0.05,
                icon="mdi:volume-high",
            ),
            VigilNumberDesc(
                key=CONF_REALERT_COOLDOWN,
                name="Re-alert cooldown",
                default=DEFAULT_REALERT_COOLDOWN,
                min_value=0,
                max_value=600,
                step=5,
                unit=UnitOfTime.SECONDS,
                icon="mdi:timer-refresh",
            ),
            VigilNumberDesc(
                key=CONF_TRIP_WEIGHT,
                name="Trip weight",
                default=DEFAULT_TRIP_WEIGHT,
                min_value=1,
                max_value=50,
                step=1,
                icon="mdi:weight",
            ),
            VigilNumberDesc(
                key=CONF_CONCURRENCY_WEIGHT,
                name="Concurrency weight",
                default=DEFAULT_CONCURRENCY_WEIGHT,
                min_value=0,
                max_value=50,
                step=1,
                icon="mdi:weight-gram",
            ),
            VigilNumberDesc(
                key=CONF_APPROACH_BOOST,
                name="Approach boost",
                default=DEFAULT_APPROACH_BOOST,
                min_value=0,
                max_value=100,
                step=5,
                icon="mdi:cctv",
            ),
            VigilNumberDesc(
                key=CONF_APPROACH_WINDOW_S,
                name="Approach window",
                default=DEFAULT_APPROACH_WINDOW_S,
                min_value=0,
                max_value=600,
                step=5,
                unit=UnitOfTime.SECONDS,
                icon="mdi:timer-outline",
            ),
        ]
    )
    return descs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VigilConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vigil tunable numbers."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        VigilNumber(coordinator, desc) for desc in _build_descriptors()
    )


class VigilNumber(VigilEntity, NumberEntity):
    """A single live-tunable value backed by the coordinator's store."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, desc: VigilNumberDesc) -> None:
        super().__init__(coordinator)
        self._desc = desc
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{desc.key}"
        self._attr_name = desc.name
        self._attr_native_min_value = desc.min_value
        self._attr_native_max_value = desc.max_value
        self._attr_native_step = desc.step
        self._attr_native_unit_of_measurement = desc.unit
        if desc.icon:
            self._attr_icon = desc.icon

    @property
    def native_value(self) -> float:
        return float(self.coordinator.get_tunable(self._desc.key, self._desc.default))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_tunable(self._desc.key, value)
