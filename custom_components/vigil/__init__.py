"""The Vigil confidence-based alarm integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import VigilCoordinator
from .notifications import VigilNotifier
from .response import VigilResponse

_LOGGER = logging.getLogger(__name__)


@dataclass
class VigilRuntime:
    """Objects shared across the integration for one config entry."""

    coordinator: VigilCoordinator
    response: VigilResponse
    notifier: VigilNotifier


VigilConfigEntry = ConfigEntry[VigilRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: VigilConfigEntry) -> bool:
    """Set up Vigil from a config entry."""
    coordinator = VigilCoordinator(hass, entry)
    response = VigilResponse(hass, coordinator)
    notifier = VigilNotifier(hass, coordinator)

    # Wire the coordinator's injected hooks.
    coordinator.start_response = response.start
    coordinator.stop_response = response.stop
    notifier.async_setup()

    await coordinator.async_start()

    entry.runtime_data = VigilRuntime(coordinator, response, notifier)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VigilConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime: VigilRuntime = entry.runtime_data
        runtime.notifier.async_unload()
        await runtime.coordinator.async_shutdown()
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: VigilConfigEntry) -> None:
    """Reload the entry when options change.

    Live tunables (cutpoints, volume, switches) update in place via the
    coordinator without a reload; this listener handles structural changes
    made through the options flow (sensor sets, targets, lights, etc.).
    """
    await hass.config_entries.async_reload(entry.entry_id)
