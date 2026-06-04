"""The Vigil confidence engine and alarm state machine."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import timedelta

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ARM_MODES,
    CONF_ALARM_CUTPOINT,
    CONF_ANNOUNCE_VOLUME,
    CONF_APPROACH_ALL,
    CONF_APPROACH_BOOST,
    CONF_APPROACH_SENSORS,
    CONF_APPROACH_WINDOW_S,
    CONF_CONCURRENCY_WEIGHT,
    CONF_DECAY_WINDOW_MIN,
    CONF_ENTRY_DELAY,
    CONF_EXCLUDED,
    CONF_EXIT_DELAY,
    CONF_PRESENCE_ENTITIES,
    CONF_INTERNAL_ALARM_ENABLED,
    CONF_MOBILE_NOTIFY_ENABLED,
    CONF_MONITOR_ALL,
    CONF_MONITORED_SENSORS,
    CONF_NOTIFY_CUTPOINT,
    CONF_REALERT_COOLDOWN,
    CONF_TEST_MODE,
    CONF_TRIP_WEIGHT,
    DECAY_TICK_S,
    DEFAULT_ANNOUNCE_VOLUME,
    DEFAULT_APPROACH_BOOST,
    DEFAULT_APPROACH_WINDOW_S,
    DEFAULT_CONCURRENCY_WEIGHT,
    DEFAULT_CUTPOINTS,
    DEFAULT_DECAY_WINDOW_MIN,
    DEFAULT_ENTRY_DELAY,
    DEFAULT_EXIT_DELAY,
    DEFAULT_REALERT_COOLDOWN,
    DEFAULT_TRIP_WEIGHT,
    DOMAIN,
    SAFETY_CAP_S,
    SCORE_MAX,
    SCORE_MIN,
    TIER_ALARM,
    TIER_NONE,
    TIER_NOTIFY,
)
from .discovery import discover_motion_sensors, discover_person_sensors

_LOGGER = logging.getLogger(__name__)

# Map an arming mode to the AlarmControlPanelState it produces.
_MODE_TO_STATE = {
    "away": AlarmControlPanelState.ARMED_AWAY,
    "home": AlarmControlPanelState.ARMED_HOME,
    "night": AlarmControlPanelState.ARMED_NIGHT,
    "vacation": AlarmControlPanelState.ARMED_VACATION,
}


class VigilCoordinator(DataUpdateCoordinator[None]):
    """Owns confidence scoring, the alarm state machine, and escalation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry

        # Live-tunable values (cutpoints, weights, switches) persisted in their
        # own Store so changing a slider does NOT reload the config entry.
        self.tunables: dict = {}
        self._store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.tunables")

        # State machine
        self.alarm_state: AlarmControlPanelState = AlarmControlPanelState.DISARMED
        self.armed_mode: str | None = None

        # Confidence engine
        self.score: float = 0.0
        self.tier: str = TIER_NONE
        self.alerting: bool = False
        self.sounding: bool = False
        self._last_activity: float = 0.0
        self._last_recompute: float = 0.0
        self._active_sensors: set[str] = set()
        self._approach_active: set[str] = set()
        self._last_approach: float = 0.0
        self._last_alert_at: float = 0.0
        self.last_trip_name: str | None = None

        # Timer / listener cancel handles
        self._unsub_sensors: Callable[[], None] | None = None
        self._unsub_presence: Callable[[], None] | None = None
        self._unsub_tick: Callable[[], None] | None = None
        self._cancel_arming: Callable[[], None] | None = None
        self._cancel_pending: Callable[[], None] | None = None
        self._cancel_safety: Callable[[], None] | None = None

        # Injected by the response orchestrator (response.py) at platform setup.
        self.start_response: Callable[[], None] | None = None
        self.stop_response: Callable[[], None] | None = None
        # Injected by the notification handler (__init__.py).
        self.send_alert: Callable[[str, float], None] | None = None

    # ------------------------------------------------------------------
    # Config / tunable accessors
    # ------------------------------------------------------------------
    @property
    def _data(self) -> dict:
        return self.entry.data

    @property
    def _options(self) -> dict:
        return self.entry.options

    def get_config(self, key: str, default=None):
        """Read a structural config value (data first, then options)."""
        if key in self._options:
            return self._options[key]
        return self._data.get(key, default)

    def get_tunable(self, key: str, default=None):
        """Read a live-tunable value from the runtime store."""
        return self.tunables.get(key, default)

    async def async_set_tunable(self, key: str, value) -> None:
        """Persist a live-tunable value and refresh listeners (no entry reload)."""
        self.tunables[key] = value
        await self._store.async_save(self.tunables)
        self.async_update_listeners()

    def _master_sensors(self) -> list[str]:
        """All candidate indoor sensors (auto-all, or the explicit list)."""
        if self.get_config(CONF_MONITOR_ALL, True):
            return discover_motion_sensors(self.hass)
        return list(self.get_config(CONF_MONITORED_SENSORS, []) or [])

    def monitored_sensors(self, mode: str | None) -> list[str]:
        """Master monitored set minus this mode's exclusions."""
        if mode is None:
            return []
        excluded = set(self.get_config(f"{CONF_EXCLUDED}_{mode}", []) or [])
        return [s for s in self._master_sensors() if s not in excluded]

    def approach_sensors(self) -> list[str]:
        """Outdoor person/approach sensors that boost (not trigger) the score."""
        if self.get_config(CONF_APPROACH_ALL, True):
            return discover_person_sensors(self.hass)
        return list(self.get_config(CONF_APPROACH_SENSORS, []) or [])

    def cutpoints(self, mode: str) -> tuple[float, float]:
        """Return (notify, alarm) cutpoints for a mode."""
        defaults = DEFAULT_CUTPOINTS[mode]
        notify = float(
            self.get_tunable(
                f"{CONF_NOTIFY_CUTPOINT}_{mode}", defaults[CONF_NOTIFY_CUTPOINT]
            )
        )
        alarm = float(
            self.get_tunable(
                f"{CONF_ALARM_CUTPOINT}_{mode}", defaults[CONF_ALARM_CUTPOINT]
            )
        )
        return notify, alarm

    @property
    def test_mode(self) -> bool:
        return bool(self.get_tunable(CONF_TEST_MODE, False))

    @property
    def decay_window_s(self) -> float:
        return (
            float(self.get_tunable(CONF_DECAY_WINDOW_MIN, DEFAULT_DECAY_WINDOW_MIN))
            * 60.0
        )

    @property
    def announce_volume(self) -> float:
        return float(self.get_tunable(CONF_ANNOUNCE_VOLUME, DEFAULT_ANNOUNCE_VOLUME))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def async_start(self) -> None:
        """Load tunables and begin watching presence for auto-disarm."""
        stored = await self._store.async_load()
        if stored:
            self.tunables = stored
        self._subscribe_presence()

    async def async_shutdown(self) -> None:
        """Tear down all listeners and timers."""
        self._cancel_all_timers()
        self._unsubscribe_sensors()
        if self._unsub_presence:
            self._unsub_presence()
            self._unsub_presence = None
        if self.stop_response:
            self.stop_response()

    @callback
    def _cancel_all_timers(self) -> None:
        for attr in ("_cancel_arming", "_cancel_pending", "_cancel_safety", "_unsub_tick"):
            cancel = getattr(self, attr)
            if cancel:
                cancel()
                setattr(self, attr, None)

    # ------------------------------------------------------------------
    # Arm / disarm state machine
    # ------------------------------------------------------------------
    async def async_arm(self, mode: str, *, skip_delay: bool = False) -> None:
        """Arm into a mode, honouring the exit delay."""
        if mode not in ARM_MODES:
            raise ValueError(f"Unknown arm mode: {mode}")
        self._reset_score()
        self.armed_mode = mode
        exit_delay = int(self.get_config(CONF_EXIT_DELAY, DEFAULT_EXIT_DELAY))

        if skip_delay or exit_delay <= 0:
            self._enter_armed()
        else:
            self.alarm_state = AlarmControlPanelState.ARMING
            self.async_update_listeners()

            @callback
            def _armed(_now) -> None:
                self._cancel_arming = None
                self._enter_armed()

            self._cancel_arming = async_call_later(self.hass, exit_delay, _armed)

    @callback
    def _enter_armed(self) -> None:
        """Transition into the live armed state and start scoring."""
        assert self.armed_mode is not None
        self.alarm_state = _MODE_TO_STATE[self.armed_mode]
        self._reset_score()
        self._subscribe_sensors()
        self._start_tick()
        self.async_update_listeners()
        _LOGGER.debug("Vigil armed: %s", self.armed_mode)

    async def async_disarm(self) -> None:
        """Disarm and clear everything."""
        self._cancel_all_timers()
        self._unsubscribe_sensors()
        if self.stop_response:
            self.stop_response()
        self.alarm_state = AlarmControlPanelState.DISARMED
        self.armed_mode = None
        self.sounding = False
        self.alerting = False
        self.tier = TIER_NONE
        self._reset_score()
        self.async_update_listeners()
        _LOGGER.debug("Vigil disarmed")

    async def async_trigger(self) -> None:
        """Force the full alarm immediately (manual panic)."""
        self._go_triggered(manual=True)

    @callback
    def _reset_score(self) -> None:
        self.score = 0.0
        self.tier = TIER_NONE
        self.alerting = False
        self._active_sensors = set()
        self._approach_active = set()
        self._last_approach = 0.0
        self._last_activity = 0.0
        self._last_alert_at = 0.0

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    @property
    def _scoring_active(self) -> bool:
        """Score while armed (any mode) or while test mode is on."""
        return self.armed_mode is not None and (
            self.alarm_state
            in (
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_HOME,
                AlarmControlPanelState.ARMED_NIGHT,
                AlarmControlPanelState.ARMED_VACATION,
                AlarmControlPanelState.PENDING,
            )
            or self.test_mode
        )

    @callback
    def _subscribe_sensors(self) -> None:
        self._unsubscribe_sensors()
        sensors = self.monitored_sensors(self.armed_mode)
        if not sensors:
            _LOGGER.warning("Vigil armed in %s with no monitored sensors", self.armed_mode)
        watched = list(dict.fromkeys(sensors + self.approach_sensors()))
        if not watched:
            return
        self._unsub_sensors = async_track_state_change_event(
            self.hass, watched, self._handle_sensor_event
        )

    @callback
    def _unsubscribe_sensors(self) -> None:
        if self._unsub_sensors:
            self._unsub_sensors()
            self._unsub_sensors = None

    @callback
    def _start_tick(self) -> None:
        if self._unsub_tick:
            return
        self._last_recompute = time.monotonic()
        self._unsub_tick = async_track_time_interval(
            self.hass, self._handle_tick, timedelta(seconds=DECAY_TICK_S)
        )

    @callback
    def _handle_sensor_event(self, event: Event) -> None:
        """A monitored or approach sensor changed state."""
        if not self._scoring_active:
            return
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        if new is None:
            return
        entity_id = event.data["entity_id"]
        approach_set = set(self.approach_sensors())

        # Approach sensors don't trip the alarm; they mark that a person was seen
        # approaching, which boosts indoor movement scored around the same time.
        if entity_id in approach_set:
            if new.state == "on":
                self._approach_active.add(entity_id)
                self._last_approach = time.monotonic()
            else:
                self._approach_active.discard(entity_id)
            return

        if new.state == "on":
            self._active_sensors.add(entity_id)
            # Count a trip only on an off->on edge (not on re-reports of "on").
            if old is None or old.state != "on":
                trip_weight = float(self.get_tunable(CONF_TRIP_WEIGHT, DEFAULT_TRIP_WEIGHT))
                concurrency_weight = float(
                    self.get_tunable(CONF_CONCURRENCY_WEIGHT, DEFAULT_CONCURRENCY_WEIGHT)
                )
                bonus = concurrency_weight * max(0, len(self._active_sensors) - 1)
                self._add_score(trip_weight + bonus + self._approach_bonus())
                self.last_trip_name = new.name or entity_id
        else:
            self._active_sensors.discard(entity_id)

    @callback
    def _approach_bonus(self) -> float:
        """Extra score when a person was detected approaching recently."""
        boost = float(self.get_tunable(CONF_APPROACH_BOOST, DEFAULT_APPROACH_BOOST))
        if not boost:
            return 0.0
        window = float(
            self.get_tunable(CONF_APPROACH_WINDOW_S, DEFAULT_APPROACH_WINDOW_S)
        )
        recent = self._last_approach and (time.monotonic() - self._last_approach) <= window
        if self._approach_active or recent:
            return boost
        return 0.0

    @callback
    def _add_score(self, amount: float) -> None:
        self.score = min(SCORE_MAX, max(SCORE_MIN, self.score + amount))
        self._last_activity = time.monotonic()
        self._evaluate()

    @callback
    def _handle_tick(self, _now) -> None:
        """Decay the score linearly toward zero over the decay window."""
        if not self._scoring_active:
            return
        now = time.monotonic()
        elapsed = now - self._last_recompute
        self._last_recompute = now
        window = self.decay_window_s
        if self.score > 0 and window > 0:
            # Lose the full score over one empty window.
            self.score = max(SCORE_MIN, self.score - (SCORE_MAX * elapsed / window))
        self._evaluate()

    # ------------------------------------------------------------------
    # Tier evaluation / escalation
    # ------------------------------------------------------------------
    @callback
    def _evaluate(self) -> None:
        """Compare the score to the current mode's cutpoints and escalate."""
        if self.armed_mode is None:
            self.async_update_listeners()
            return
        notify_cut, alarm_cut = self.cutpoints(self.armed_mode)

        previous_tier = self.tier
        if self.score >= alarm_cut:
            self.tier = TIER_ALARM
        elif self.score >= notify_cut:
            self.tier = TIER_NOTIFY
        else:
            self.tier = TIER_NONE
            self.alerting = False

        if self.tier == TIER_NOTIFY and self.alarm_state not in (
            AlarmControlPanelState.PENDING,
            AlarmControlPanelState.TRIGGERED,
        ):
            self._maybe_notify(previous_tier)
        elif self.tier == TIER_ALARM and self.alarm_state not in (
            AlarmControlPanelState.PENDING,
            AlarmControlPanelState.TRIGGERED,
        ):
            self._begin_alarm()

        self.async_update_listeners()

    @callback
    def _maybe_notify(self, previous_tier: str) -> None:
        """Send the tier-1 heads-up, respecting the re-alert cooldown."""
        self.alerting = True
        if not bool(self.get_tunable(CONF_MOBILE_NOTIFY_ENABLED, True)):
            return
        cooldown = float(self.get_tunable(CONF_REALERT_COOLDOWN, DEFAULT_REALERT_COOLDOWN))
        now = time.monotonic()
        if previous_tier == TIER_NOTIFY and (now - self._last_alert_at) < cooldown:
            return
        self._last_alert_at = now
        if self.send_alert and not self.test_mode:
            self.send_alert("notify", self.score)
        _LOGGER.debug("Vigil tier-1 notify at score %.0f", self.score)

    @callback
    def _begin_alarm(self) -> None:
        """Tier-2: either go straight to triggered or use the entry-delay grace."""
        entry_delay = int(self.get_config(CONF_ENTRY_DELAY, DEFAULT_ENTRY_DELAY))
        if entry_delay <= 0:
            self._go_triggered()
            return
        self.alarm_state = AlarmControlPanelState.PENDING
        if self.send_alert and not self.test_mode:
            self.send_alert("pending", self.score)

        @callback
        def _fire(_now) -> None:
            self._cancel_pending = None
            self._go_triggered()

        self._cancel_pending = async_call_later(self.hass, entry_delay, _fire)
        self.async_update_listeners()

    @callback
    def _go_triggered(self, *, manual: bool = False) -> None:
        """Enter the full-alarm state and run the response orchestrator."""
        if self._cancel_pending:
            self._cancel_pending()
            self._cancel_pending = None
        self.alarm_state = AlarmControlPanelState.TRIGGERED
        self.tier = TIER_ALARM
        internal_enabled = bool(self.get_tunable(CONF_INTERNAL_ALARM_ENABLED, True))

        if self.send_alert and not self.test_mode:
            self.send_alert("alarm", self.score)

        if internal_enabled and not self.test_mode:
            self.sounding = True
            if self.start_response:
                self.start_response()

            # Safety cap: silence after SAFETY_CAP_S even if nobody disarms.
            @callback
            def _cap(_now) -> None:
                self._cancel_safety = None
                self.sounding = False
                if self.stop_response:
                    self.stop_response()
                self.async_update_listeners()

            self._cancel_safety = async_call_later(self.hass, SAFETY_CAP_S, _cap)

        _LOGGER.warning(
            "Vigil FULL ALARM (score %.0f, mode %s%s)",
            self.score,
            self.armed_mode,
            ", manual" if manual else "",
        )
        self.async_update_listeners()

    # ------------------------------------------------------------------
    # Presence-based auto-disarm
    # ------------------------------------------------------------------
    @callback
    def _subscribe_presence(self) -> None:
        entities = self.get_config(CONF_PRESENCE_ENTITIES, []) or []
        if not entities:
            return
        self._unsub_presence = async_track_state_change_event(
            self.hass, list(entities), self._handle_presence_event
        )

    @callback
    def _handle_presence_event(self, event: Event) -> None:
        if self.alarm_state == AlarmControlPanelState.DISARMED:
            return
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        if new is None or old is None:
            return
        if new.state == "home" and old.state != "home":
            _LOGGER.debug("Vigil auto-disarm: %s arrived home", event.data["entity_id"])
            self.hass.async_create_task(self.async_disarm())
