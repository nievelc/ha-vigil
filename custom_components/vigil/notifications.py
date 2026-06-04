"""Actionable mobile notifications and their action handler."""

from __future__ import annotations

import logging

from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    ACTION_DISARM,
    ACTION_DISMISS,
    ACTION_TRIGGER,
    CONF_CAMERA,
    CONF_NOTIFY_TARGETS,
    EVENT_MOBILE_ACTION,
    NOTIFY_TAG,
)
from .coordinator import VigilCoordinator

_LOGGER = logging.getLogger(__name__)

_TITLES = {
    "notify": "⚠️ Vigil — movement detected",
    "pending": "🚨 Vigil — alarm imminent",
    "alarm": "🚨 Vigil — INTRUDER ALARM",
}


class VigilNotifier:
    """Builds Vigil push notifications and handles their button actions."""

    def __init__(self, hass: HomeAssistant, coordinator: VigilCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._unsub_action = None

    @callback
    def async_setup(self) -> None:
        """Wire the coordinator's send_alert hook and listen for action taps."""
        self.coordinator.send_alert = self.send
        self._unsub_action = self.hass.bus.async_listen(
            EVENT_MOBILE_ACTION, self._handle_action
        )

    @callback
    def async_unload(self) -> None:
        if self._unsub_action:
            self._unsub_action()
            self._unsub_action = None
        self.coordinator.send_alert = None

    # ------------------------------------------------------------------
    @callback
    def send(self, kind: str, score: float) -> None:
        """Push an actionable notification to all configured targets."""
        targets = self.coordinator.get_config(CONF_NOTIFY_TARGETS, []) or []
        if not targets:
            return

        mode = self.coordinator.armed_mode or "?"
        title = _TITLES.get(kind, "Vigil alert")
        last = self.coordinator.last_trip_name or "a sensor"
        message = (
            f"Confidence {score:.0f}/100 while armed ({mode}). "
            f"Last movement: {last}."
        )
        if kind == "pending":
            message += " Disarm now or the alarm will sound."

        data: dict = {
            "tag": NOTIFY_TAG,
            "actions": [
                {"action": ACTION_DISARM, "title": "Disarm"},
                {"action": ACTION_DISMISS, "title": "It's fine"},
                {"action": ACTION_TRIGGER, "title": "Intruder!"},
            ],
        }
        # Critical/loud for the real alarm tiers.
        if kind in ("pending", "alarm"):
            data["push"] = {
                "interruption-level": "critical",  # iOS
                "sound": {"name": "default", "critical": 1, "volume": 1.0},
            }
            data["priority"] = "high"  # Android
            data["ttl"] = 0

        camera = self.coordinator.get_config(CONF_CAMERA)
        if camera:
            data["entity_id"] = camera  # attaches a camera snapshot on mobile_app

        for target in targets:
            service = target.replace("notify.", "")
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "notify",
                    service,
                    {"title": title, "message": message, "data": data},
                    blocking=False,
                )
            )

    # ------------------------------------------------------------------
    @callback
    def _handle_action(self, event: Event) -> None:
        action = event.data.get("action")
        if action == ACTION_DISARM:
            self.hass.async_create_task(self.coordinator.async_disarm())
        elif action == ACTION_DISMISS:
            self.hass.async_create_task(self.coordinator.async_disarm())
        elif action == ACTION_TRIGGER:
            self.hass.async_create_task(self.coordinator.async_trigger())
