# PWM Climate Controller

This directory contains the Home Assistant custom integration for
`pwm_climate`. The integration creates a climate entity that calculates
proportional heat demand and applies it through software PWM or a numeric output
value.

For the full project documentation, see the repository [README](../../README.md).

## Quick Reference

| Item | Value |
| --- | --- |
| Domain | `pwm_climate` |
| Platform | `climate` |
| Setup | UI config flow |
| Minimum Home Assistant | `2024.1.0` |
| Manifest version | `0.1.2` |
| License | Apache License 2.0 |

## Supported Output Entities

| Domain | Behavior |
| --- | --- |
| `switch`, `input_boolean`, `light` | Turned on/off according to the PWM phase. |
| `number`, `input_number` | Receives the calculated duty cycle percentage with `set_value`. |
| `climate` | Gets the controller target temperature while on and is turned off while off. |

## Configuration

Add the integration from Settings -> Devices & services -> Add integration ->
PWM Climate Controller.

Required setup fields:

- Name
- Temperature sensor entity
- Output entity
- Default preset
- Proportional gain (`Kp`)

Optional setup fields:

- Humidity sensor entity
- Min/max target temperature
- Target temperature step
- PWM period in seconds
- Target temperature per preset

The options flow (Settings -> Devices & services -> PWM Climate Controller ->
Configure) lets you change the temperature source and optional humidity source
independently, plus tuning and preset temperatures. Temperature accepts sensors
with temperature device class or °C unit. Humidity accepts humidity device class
or classless % unit. Clear humidity to remove its source permanently, including
after restart. Saving applies immediately without deleting the climate entity or
restarting Home Assistant, preserving its identity, output, other saved options,
HVAC mode and manual target. Invalid new temperature clears the reading and
forces zero heat demand; invalid new humidity clears its display. YAML
configuration is not required.

Existing humidity sources selected by older releases remain usable while the
source still exists as a sensor, even without humidity metadata. New choices
are limited to humidity measurements.

## Control Summary

The controller calculates demand with:

```text
output = clamp(Kp * (target_temperature - current_temperature), 0, 100)
```

That output becomes the PWM duty cycle. HVAC `off`, missing current
temperature, and the `Ochrana budovy` no-heat preset force the output to `0 %`.
Manual target temperature changes switch the entity to the internal `manual`
preset state until another preset is selected.

## Debug Logging

```yaml
logger:
  default: warning
  logs:
    custom_components.pwm_climate: debug
```
