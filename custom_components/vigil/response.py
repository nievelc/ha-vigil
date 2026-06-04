"""Response orchestrator: flashing lights + repeating spoken deterrent.

Ports the behaviour of the old ``script.alarm_full_response`` into the
integration. While the alarm is sounding it runs two concurrent loops:
  1. flash the colour lights red <-> blue and toggle the flash lights;
  2. repeat the spoken deterrent on the enabled speakers every ~10s.
The 10-minute safety cap that stops the alarm lives in the coordinator.
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant, callback

from .const import (
    ANNOUNCE_INTERVAL_S,
    CONF_INTRUDER_MESSAGE,
    CONF_SPEAKER_ENABLED,
    CONF_SPEAKERS,
    CONF_TTS_ENGINE,
    CONF_TTS_VOICE,
    DEFAULT_INTRUDER_MESSAGE,
    DEFAULT_TTS_ENGINE,
    FLASH_INTERVAL_S,
)
from .coordinator import VigilCoordinator

_LOGGER = logging.getLogger(__name__)


class VigilResponse:
    """Drives lights + TTS while the alarm sounds."""

    def __init__(self, hass: HomeAssistant, coordinator: VigilCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    @callback
    def start(self) -> None:
        """Start the flash and announce loops (idempotent)."""
        self.stop()
        self._tasks = [
            self.hass.async_create_task(self._flash_loop()),
            self.hass.async_create_task(self._announce_loop()),
        ]

    @callback
    def stop(self) -> None:
        """Cancel loops and switch the lights off."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks = []
        self.coordinator.sounding = False
        self.hass.async_create_task(self._lights_off())

    # ------------------------------------------------------------------
    def _colour_lights(self) -> list[str]:
        return list(self.coordinator.get_config("colour_lights", []) or [])

    def _flash_lights(self) -> list[str]:
        return list(self.coordinator.get_config("flash_lights", []) or [])

    def _enabled_speakers(self) -> list[str]:
        speakers = list(self.coordinator.get_config(CONF_SPEAKERS, []) or [])
        enabled: list[str] = []
        for entity_id in speakers:
            key = f"{CONF_SPEAKER_ENABLED}_{entity_id}"
            if bool(self.coordinator.get_tunable(key, True)):
                enabled.append(entity_id)
        return enabled

    # ------------------------------------------------------------------
    async def _flash_loop(self) -> None:
        colour = self._colour_lights()
        flash = self._flash_lights()
        try:
            while self.coordinator.sounding:
                if colour:
                    await self._call(
                        "light", "turn_on",
                        {"entity_id": colour, "rgb_color": [255, 0, 0],
                         "brightness": 255, "transition": 0},
                    )
                if flash:
                    await self._call("light", "turn_on", {"entity_id": flash})
                await asyncio.sleep(FLASH_INTERVAL_S)
                if colour:
                    await self._call(
                        "light", "turn_on",
                        {"entity_id": colour, "rgb_color": [0, 0, 255],
                         "brightness": 255, "transition": 0},
                    )
                if flash:
                    await self._call("light", "turn_off", {"entity_id": flash})
                await asyncio.sleep(FLASH_INTERVAL_S)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - keep the loop alive on transient errors
            _LOGGER.exception("Vigil flash loop error")

    async def _announce_loop(self) -> None:
        engine = self.coordinator.get_config(CONF_TTS_ENGINE, DEFAULT_TTS_ENGINE)
        voice = self.coordinator.get_config(CONF_TTS_VOICE)
        message = self.coordinator.get_config(
            CONF_INTRUDER_MESSAGE, DEFAULT_INTRUDER_MESSAGE
        )
        if self.coordinator.test_mode:
            message = f"This is a test. {message}"
        try:
            while self.coordinator.sounding:
                speakers = self._enabled_speakers()
                if speakers and engine:
                    await self._set_volume(speakers)
                    data = {
                        "media_player_entity_id": speakers,
                        "message": message,
                    }
                    if voice:
                        data["options"] = {"voice": voice}
                    await self._call(
                        "tts", "speak", {"entity_id": engine, **data}
                    )
                await asyncio.sleep(ANNOUNCE_INTERVAL_S)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Vigil announce loop error")

    async def _set_volume(self, speakers: list[str]) -> None:
        await self._call(
            "media_player", "volume_set",
            {"entity_id": speakers, "volume_level": self.coordinator.announce_volume},
        )

    async def _lights_off(self) -> None:
        targets = self._colour_lights() + self._flash_lights()
        if targets:
            await self._call("light", "turn_off", {"entity_id": targets})

    async def _call(self, domain: str, service: str, data: dict) -> None:
        await self.hass.services.async_call(
            domain, service, data, blocking=False
        )
