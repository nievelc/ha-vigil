"""Constants for the Vigil alarm integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "vigil"

# ---------------------------------------------------------------------------
# Arming modes
# ---------------------------------------------------------------------------
MODE_AWAY: Final = "away"
MODE_HOME: Final = "home"
MODE_NIGHT: Final = "night"
MODE_VACATION: Final = "vacation"
ARM_MODES: Final = (MODE_AWAY, MODE_HOME, MODE_NIGHT, MODE_VACATION)

# Friendly labels (used in entity names / UI)
MODE_LABELS: Final = {
    MODE_AWAY: "Away",
    MODE_HOME: "Home",
    MODE_NIGHT: "Night",
    MODE_VACATION: "Vacation",
}

# ---------------------------------------------------------------------------
# Escalation tiers
# ---------------------------------------------------------------------------
TIER_NONE: Final = "none"
TIER_NOTIFY: Final = "notify"
TIER_ALARM: Final = "alarm"

# ---------------------------------------------------------------------------
# Config-flow / options keys (structural — set in the UI dialog)
# ---------------------------------------------------------------------------
# One master monitored-sensor list; each mode watches all of them MINUS its
# per-mode exclusion list (keyed f"{CONF_EXCLUDED}_{mode}"). Adding a sensor to
# the master list applies it to every mode automatically.
CONF_MONITORED_SENSORS: Final = "monitored_sensors"
# When True (default), Vigil auto-watches every motion/occupancy binary_sensor
# and CONF_MONITORED_SENSORS is ignored — "select all", no picking required.
CONF_MONITOR_ALL: Final = "monitor_all_motion"
# Sensors never monitored in ANY mode (e.g. an outdoor motion sensor that
# slips through auto-discovery). Applied on top of monitor-all / explicit list.
CONF_GLOBAL_EXCLUDE: Final = "excluded_global"
CONF_EXCLUDED: Final = "excluded"  # used as f"{CONF_EXCLUDED}_{mode}"
# Outdoor person/approach sensors (e.g. Frigate *_person_occupancy). These do
# NOT count as indoor trips; instead they boost the score of indoor movement
# that happens while (or shortly after) someone is detected approaching.
CONF_APPROACH_SENSORS: Final = "approach_sensors"
# When True (default), auto-use every *_person_occupancy binary_sensor as an
# approach sensor and CONF_APPROACH_SENSORS is ignored.
CONF_APPROACH_ALL: Final = "approach_all_person"
CONF_PRESENCE_ENTITIES: Final = "presence_entities"

# Device classes treated as "movement" for auto-discovery.
MOTION_DEVICE_CLASSES: Final = ("motion", "occupancy", "moving", "presence")
# Suffix identifying an outdoor person-detection sensor (e.g. Frigate
# "<camera>_person_occupancy"). Routed to the approach booster, never monitored.
PERSON_SENSOR_HINT: Final = "person_occupancy"
# Integrations whose binary_sensors are camera object-detections (cat/dog/fox/
# car/person per zone) and must NOT be auto-watched as indoor movement.
EXCLUDED_DISCOVERY_PLATFORMS: Final = ("frigate",)
CONF_NOTIFY_TARGETS: Final = "notify_targets"
CONF_COLOUR_LIGHTS: Final = "colour_lights"
CONF_FLASH_LIGHTS: Final = "flash_lights"
CONF_SPEAKERS: Final = "speakers"  # list of media_player entity_ids
CONF_TTS_ENGINE: Final = "tts_engine"
CONF_TTS_VOICE: Final = "tts_voice"
CONF_CAMERA: Final = "camera"
CONF_EXIT_DELAY: Final = "exit_delay"
CONF_ENTRY_DELAY: Final = "entry_delay"
CONF_CODE: Final = "code"
CONF_CODE_ARM_REQUIRED: Final = "code_arm_required"
CONF_INTRUDER_MESSAGE: Final = "intruder_message"

# ---------------------------------------------------------------------------
# Tunable keys (live — exposed as number/switch entities, persisted in options)
# ---------------------------------------------------------------------------
# Per-mode cutpoints: f"{CONF_NOTIFY_CUTPOINT}_{mode}" / f"{CONF_ALARM_CUTPOINT}_{mode}"
CONF_NOTIFY_CUTPOINT: Final = "notify_cutpoint"
CONF_ALARM_CUTPOINT: Final = "alarm_cutpoint"
CONF_DECAY_WINDOW_MIN: Final = "decay_window_minutes"
CONF_ANNOUNCE_VOLUME: Final = "announce_volume"
CONF_REALERT_COOLDOWN: Final = "realert_cooldown_seconds"
CONF_TRIP_WEIGHT: Final = "trip_weight"
CONF_CONCURRENCY_WEIGHT: Final = "concurrency_weight"
CONF_APPROACH_BOOST: Final = "approach_boost"
CONF_APPROACH_WINDOW_S: Final = "approach_window_seconds"

# Channel + per-speaker switches: f"{CONF_SPEAKER_ENABLED}_{entity_id}"
CONF_MOBILE_NOTIFY_ENABLED: Final = "mobile_notification_enabled"
CONF_INTERNAL_ALARM_ENABLED: Final = "internal_alarm_enabled"
CONF_SPEAKER_ENABLED: Final = "speaker_enabled"
CONF_TEST_MODE: Final = "test_mode"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
# Per-mode default cutpoints (notify, alarm). Vacation strictest (lowest), Home
# most lenient because you are inside and moving around legitimately.
DEFAULT_CUTPOINTS: Final = {
    MODE_AWAY: {CONF_NOTIFY_CUTPOINT: 40, CONF_ALARM_CUTPOINT: 75},
    MODE_HOME: {CONF_NOTIFY_CUTPOINT: 55, CONF_ALARM_CUTPOINT: 85},
    MODE_NIGHT: {CONF_NOTIFY_CUTPOINT: 35, CONF_ALARM_CUTPOINT: 70},
    MODE_VACATION: {CONF_NOTIFY_CUTPOINT: 25, CONF_ALARM_CUTPOINT: 55},
}

DEFAULT_DECAY_WINDOW_MIN: Final = 5.0
DEFAULT_ANNOUNCE_VOLUME: Final = 1.0
DEFAULT_REALERT_COOLDOWN: Final = 120
DEFAULT_TRIP_WEIGHT: Final = 12.0
DEFAULT_CONCURRENCY_WEIGHT: Final = 8.0
DEFAULT_APPROACH_BOOST: Final = 25.0
DEFAULT_APPROACH_WINDOW_S: Final = 60.0
DEFAULT_EXIT_DELAY: Final = 60
DEFAULT_ENTRY_DELAY: Final = 30
DEFAULT_TTS_ENGINE: Final = "tts.google_translate_en_com"
DEFAULT_INTRUDER_MESSAGE: Final = (
    "Warning. This property is protected and an intruder has been detected. "
    "The police have been alerted. Leave the property now."
)

SCORE_MIN: Final = 0.0
SCORE_MAX: Final = 100.0

# Response loop timing
FLASH_INTERVAL_S: Final = 0.5
ANNOUNCE_INTERVAL_S: Final = 10.0
SAFETY_CAP_S: Final = 600  # 10 minutes
DECAY_TICK_S: Final = 2.0  # how often the score is recomputed/decayed

# ---------------------------------------------------------------------------
# Events / notification actions
# ---------------------------------------------------------------------------
EVENT_ALERT: Final = "vigil_alert"  # fired on tier-1 (notify) escalation
EVENT_TRIGGERED: Final = "vigil_triggered"  # fired on tier-2 (full alarm)
EVENT_MOBILE_ACTION: Final = "mobile_app_notification_action"

ACTION_DISARM: Final = "VIGIL_DISARM"
ACTION_DISMISS: Final = "VIGIL_DISMISS"
ACTION_TRIGGER: Final = "VIGIL_TRIGGER"
NOTIFY_TAG: Final = "vigil_alarm"

# Platforms forwarded from the config entry
PLATFORMS: Final = [
    "alarm_control_panel",
    "sensor",
    "binary_sensor",
    "number",
    "switch",
]
