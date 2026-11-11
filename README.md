# PWM Climate Controller

PWM Climate Controller is a Home Assistant custom integration that exposes one
software PWM climate entity per config entry. It is designed mainly for
hydronic floor heating and other slow heating systems driven by on/off or
percentage-capable actuators.

The controller uses proportional control to calculate a 0-100 % heat demand and
then applies that demand through a software PWM timer or a numeric output value.

## Project Status

| Item | Value |
| --- | --- |
| Integration domain | `pwm_climate` |
| Platform | `climate` |
| Setup method | Home Assistant UI config flow |
| Options flow | Yes, for measurement sources, tuning and preset temperatures |
| Minimum Home Assistant version | `2024.1.0` |
| Current manifest version | `0.1.2` |
| I/O class | `local_polling` |
| License | Apache License 2.0 |

## Features

- Climate entity with `off` and `heat` HVAC modes.
- Target temperature, turn on/off, and preset mode support.
- Proportional control: `output = Kp * (target - current)`, clamped to
  `0-100 %`.
- Software PWM output with configurable period.
- Support for binary, numeric, and climate output entities.
- Optional humidity sensor display. Humidity is not used for regulation.
- Configurable min/max temperature, target step, proportional gain, PWM period,
  default preset, and target temperature per preset.
- Manual target temperature override until another preset is selected.
- Restores the previous HVAC mode, preset, target temperature, and manual
  override after Home Assistant restart.
- Diagnostic state attributes for dashboards and troubleshooting.
- Tests for config flow, output adapter, PWM timer, preset helpers, and climate
  behavior.

## Installation

### HACS

1. In HACS, add `https://github.com/JOhugo6/pwm_climate` as a custom repository
   with category `Integration`.
2. Install `PWM Climate Controller`.
3. Restart Home Assistant.
4. Go to Settings -> Devices & services -> Add integration.
5. Select `PWM Climate Controller`.

### Manual

1. Copy `custom_components/pwm_climate` into
   `<home_assistant_config>/custom_components/pwm_climate`.
2. Restart Home Assistant.
3. Go to Settings -> Devices & services -> Add integration.
4. Select `PWM Climate Controller`.

No YAML configuration is required.

## Configuration

The integration is configured from the Home Assistant UI.

### Required Fields

| Field | Description |
| --- | --- |
| Name | Name of the climate entity and registered Home Assistant device. |
| Temperature sensor entity | Must be a `sensor` with `device_class: temperature` or Celsius unit. |
| Output entity | Entity driven by the calculated PWM demand. |
| Default preset | Preset applied by default and when switching from `off` to `heat`. |
| Proportional gain (`Kp`) | Multiplier for the temperature error. |

### Optional Fields

| Field | Default | Notes |
| --- | --- | --- |
| Humidity sensor entity | unset | Display-only current humidity. Sensor with humidity device class or classless % unit. |
| Minimum temperature | `20.0` | Lower target temperature limit shown in the UI. |
| Maximum temperature | `28.0` | Upper target temperature limit shown in the UI. |
| Temperature step | `0.1` | Target temperature step shown in the UI. |
| PWM period | `900` seconds | Length of one PWM cycle. Runtime minimum is 1 second. |
| Preset temperatures | see below | Each preset has its own configurable target. |

From Settings -> Devices & services -> PWM Climate Controller -> Configure,
change the temperature source and optional humidity source independently, along
with the default preset, min/max temperature, target step, `Kp`, PWM period and
preset target temperatures. Clear the humidity field to remove its source; it
stays removed after restart even if the original setup included humidity.

Saving applies the settings immediately through the existing entry update
listener; changing sources does not require deleting the climate entity or
restarting Home Assistant. The entity ID, output, other saved options and manual
target/HVAC mode remain in place. A new source is read immediately, and events
from the previous source are ignored. Missing or invalid temperature at the time
of switching clears the reading and forces zero heat demand. Missing or invalid
humidity at the time of switching clears the displayed humidity. Humidity remains
display-only.

Existing humidity sources selected by older releases remain usable while the
source still exists as a sensor, even without humidity metadata. New choices
are limited to humidity measurements.

## Presets

Preset labels follow the KNX HVAC mode names used by the integration.

| ID | Preset | Config key | Default target |
| --- | --- | --- | --- |
| `0` | `Auto` | `hvac_auto_temperature` | `22.0 C` |
| `1` | `Komfort` | `hvac_comfort_temperature` | `24.0 C` |
| `2` | `Připraveno` | `hvac_standby_temperature` | `22.0 C` |
| `3` | `ECO` | `hvac_economy_temperature` | `21.0 C` |
| `4` | `Ochrana budovy` | `hvac_building_protection_temperature` | `8.0 C` |

Selecting a preset sets the target temperature from the preset table and clears
manual override. Setting the target temperature directly switches the entity to
the internal `manual` preset state until a preset is selected again.

`Ochrana budovy` is treated as a no-heat preset by the current controller logic,
so the output is forced off even though the preset keeps a target temperature in
the configuration.

## Output Entities

The config flow allows these output domains:

| Domain | Behavior |
| --- | --- |
| `switch`, `input_boolean`, `light` | Turned on during the PWM on phase and off during the PWM off phase. |
| `number`, `input_number` | Receives the current duty cycle percentage through `set_value`. |
| `climate` | Receives `climate.set_temperature` with the controller target while on, and `climate.turn_off` while off. |

Unsupported or missing output entities disable output control and are logged.
The adapter waits briefly for Home Assistant services and entities that may be
registered late during startup.

## Control Behavior

1. The current temperature is read from the configured temperature sensor.
2. The target temperature comes from the active preset or manual override.
3. The controller calculates:

   ```text
   error = target_temperature - current_temperature
   control_output_percent = clamp(Kp * error, 0, 100)
   duty_cycle_percent = control_output_percent
   ```

4. `off` mode, missing temperature, or the no-heat preset force the output to
   `0 %`.
5. `0 %` and `100 %` outputs are applied as fixed off/on states without a
   running PWM loop. Intermediate values run the software PWM cycle.

When Home Assistant restarts, the climate entity restores the last HVAC mode,
active preset, manual override state, and target temperature when restore state
data is available.

## Diagnostic Attributes

The climate entity exposes these extra state attributes:

- `temperature_entity`
- `output_entity`
- `humidity_entity`
- `pwm_period_seconds`
- `default_preset`
- `active_preset`
- `manual_override`
- `control_output_percent`
- `duty_cycle_percent`

## Debug Logging

Add this to `configuration.yaml` to inspect regulation and PWM decisions:

```yaml
logger:
  default: warning
  logs:
    custom_components.pwm_climate: debug
```

## Migration Note

Older releases used a different integration domain. If you already have config
entries from that older domain and need to preserve entity IDs, update Home
Assistant storage before restarting with this version:

1. Stop Home Assistant.
2. Back up the `.storage` directory.
3. In `.storage/core.config_entries`, locate entries that contain
   `temperature_entity`, `output_entity`, and `pwm_period`, then set their
   `domain` to `pwm_climate`.
4. In `.storage/core.entity_registry`, locate entities with the same
   `config_entry_id` and set their `platform` to `pwm_climate`.
5. Start Home Assistant.

## Development

The repository layout is intentionally small:

| Path | Purpose |
| --- | --- |
| `custom_components/pwm_climate/` | Home Assistant integration source. |
| `custom_components/pwm_climate/translations/` | English and Czech UI strings. |
| `tests/` | Unit tests with lightweight Home Assistant stubs. |
| `docs/PRDs/` | Work-item implementation and traceability records. |

Run the test suite from the repository root:

```powershell
python -m pytest
```

Install `pytest` and `voluptuous` first if it is not available in your active Python
environment.
