# Vigil — confidence-based alarm for Home Assistant

Vigil is a self-contained Home Assistant custom integration that turns your
existing motion/presence sensors into a real intruder alarm — without a physical
siren, contact sensors, or camera corroboration.

Instead of "a sensor tripped → sound the alarm" (which a roaming pet or a
draught sets off), Vigil computes a single **0–100 confidence score** from how
much movement is happening and how it builds over time, then escalates in two
tiers:

1. **Notify** — a quiet, actionable push ("movement detected, confidence 45/100")
   with **Disarm / It's fine / Intruder!** buttons.
2. **Full alarm** — continuous red/blue light flashing + a repeating spoken
   deterrent on your speakers, with a 10-minute safety cap.

It exposes a native `alarm_control_panel` entity, so the standard Lovelace alarm
card and any automation that understands alarm panels just work.

## Why a score instead of thresholds?

- **Pet-proof by design** — a single isolated trip barely moves the score; it
  takes sustained or multi-room movement to cross a cutpoint. Fine for cats. For
  larger pets (dogs) that genuinely roam, turn on **human-detection-only** mode
  so the score counts only person-detecting sensors (mmWave human-presence or
  camera person events).
- **Camera-independent** — answers "someone bypassed the cameras but is walking
  around inside" using motion alone.
- **One number to tune** — `sensor.vigil_confidence`. Notify at X, sound at Y.

## Features

- Native `alarm_control_panel` with **Away / Home / Night / Vacation** modes.
  Pick your monitored sensors **once**; every mode watches all of them, and you
  optionally **exclude** specific sensors per mode (e.g. Home ignores the lounge).
  Add a sensor later and it applies to every mode automatically.
- Unified confidence engine: per-sensor trips accumulate, concurrent activity
  adds weight, and the score decays over a window of stillness.
- **Approach booster** — feed outdoor person-detection sensors (e.g. Frigate
  `*_person_occupancy`) and indoor movement seen while someone is detected
  approaching scores higher. Indoor sensors still score on their own, so it stays
  camera-independent; the boost just helps separate "a person approached then
  movement inside" from "the dog is wandering about".
- Two-tier escalation with **per-mode** notify/alarm cutpoints.
- Actionable, cross-platform push notifications (Android + iOS), optional camera
  snapshot attached.
- Continuous light-flash + spoken-deterrent response, fully configurable
  (which lights, which speakers, message, volume, TTS engine).
- Presence-based **auto-disarm** when a chosen person/device_tracker arrives.
- **Test mode** to walk-test scoring without anything sounding.
- Everything tunable from the dashboard via integration-owned `number`/`switch`
  entities — no YAML.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/nievelc/ha-vigil` as an **Integration**.
3. Install **Vigil**, then **restart Home Assistant**.
4. Settings → Devices & Services → **Add Integration** → **Vigil**.
5. Walk through the three setup steps (core settings → sensors → outputs &
   response).

## Entities created

| Entity | Purpose |
| --- | --- |
| `alarm_control_panel.vigil` | Arm/disarm, shows state + confidence attribute |
| `sensor.vigil_confidence` | The 0–100 score |
| `sensor.vigil_active_sensors` | How many monitored sensors are active now (diagnostic) |
| `binary_sensor.vigil_alerting` | On during the notify tier |
| `number.vigil_*` | Per-mode cutpoints, decay window, volume, weights, cooldown |
| `switch.vigil_*` | Channel enables, test mode, per-speaker toggles |

## Tuning

Start with the defaults and run **Test mode** on while you walk the house:
watch `sensor.vigil_confidence` climb and decay. Adjust the per-mode
**notify cutpoint** and **alarm cutpoint** numbers until the heads-up fires when
you want it and the full alarm only fires on genuine sustained movement.

## Roadmap (v2)

- Plate-based auto-disarm (Frigate LPR).
- Frigate boundary/outer-ring weighting (approachers vs. passers-by).
- Bayesian household-mode estimator.

## License

MIT — see [LICENSE](LICENSE).
