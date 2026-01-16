# PWM Climate Controller - Home Assistant Custom Integration

PWM Climate Controller is a proportional PWM-based climate controller designed primarily for hydronic floor heating systems.

## Control Algorithm
This integration uses proportional (P) control with PWM output.
It does NOT implement a full PID controller.

## Features
- Climate entity compatible with Home Assistant UI
- Proportional control based on current vs target temperature
- PWM output for on/off actuators (relays, thermal actuators, KNX outputs)
- Optional humidity sensor display
- Configurable min/max temperature, step, and PWM period
- Preset temperatures per HVAC mode
- Fully async execution

## Installation
### Manual
1. Copy `custom_components/pwm_climate` into `<config>/custom_components/`.
2. Restart Home Assistant.
3. Add the integration in UI: Settings -> Devices & Services -> Add Integration -> PWM Climate Controller.

## Configuration
This integration uses Config Flow; no YAML is required.

### Required
- Name
- Temperature sensor entity
- Output entity (`number`, `switch`, or `light`)

### Optional
- Humidity sensor entity
- Min/Max temperature
- Temperature step
- PWM period
- Preset temperatures per HVAC mode

## Control Notes
- Humidity is display-only and does not affect control.
- The output entity is driven by PWM duty cycle.

## Breaking Changes
This release renames the integration domain to `pwm_climate`.
To preserve existing config entries and entity IDs, update Home Assistant storage before restarting:
1. Stop Home Assistant.
2. Back up the `.storage` directory.
3. In `.storage/core.config_entries`, locate entries that contain `temperature_entity`, `output_entity`, and `pwm_period`, then set their `domain` to `pwm_climate`.
4. In `.storage/core.entity_registry`, locate entities with the same `config_entry_id` and set their `platform` to `pwm_climate`.
5. Start Home Assistant.

## License
MIT License
