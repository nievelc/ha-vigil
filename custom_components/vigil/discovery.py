"""Shared sensor auto-discovery for Vigil.

Frigate publishes many outdoor object-detection binary_sensors (cat/dog/fox/
car/person per camera zone), all device_class 'occupancy'. Those must never be
auto-watched as indoor movement, or a fox on the lawn would raise the alarm.
We exclude camera integrations by platform and route person sensors to the
approach booster instead.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    EXCLUDED_DISCOVERY_PLATFORMS,
    MOTION_DEVICE_CLASSES,
    PERSON_SENSOR_HINT,
)


@callback
def discover_motion_sensors(hass: HomeAssistant) -> list[str]:
    """All indoor movement sensors: motion/occupancy, excluding camera platforms."""
    reg = er.async_get(hass)
    out: list[str] = []
    for state in hass.states.async_all("binary_sensor"):
        eid = state.entity_id
        if eid.endswith(f"_{PERSON_SENSOR_HINT}"):
            continue  # person detections belong to the approach booster
        entry = reg.async_get(eid)
        if entry and entry.platform in EXCLUDED_DISCOVERY_PLATFORMS:
            continue  # skip Frigate/camera object sensors
        if state.attributes.get("device_class") in MOTION_DEVICE_CLASSES:
            out.append(eid)
    return sorted(out)


@callback
def discover_person_sensors(hass: HomeAssistant) -> list[str]:
    """All outdoor person-detection sensors (e.g. Frigate *_person_occupancy)."""
    return sorted(
        state.entity_id
        for state in hass.states.async_all("binary_sensor")
        if state.entity_id.endswith(f"_{PERSON_SENSOR_HINT}")
    )
