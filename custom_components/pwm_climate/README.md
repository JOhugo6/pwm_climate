# PWM Climate Controller - Home Assistant Custom Integration

PWM Climate Controller is a proportional PWM-based climate controller designed primarily for hydronic floor heating systems.

## Control Algorithm
This integration uses proportional (P) control with PWM output.
It does not implement proportional-integral-derivative control; no integral or derivative terms are used.

## Features
- Climate entity compatible with the Home Assistant UI
- Proportional control based on current vs. target temperature
- PWM output suitable for on/off actuators (relays, thermal valves)
- Optional humidity sensor display (does not influence control)
- Configurable min/max temperature, temperature step, and PWM period
- Preset target temperatures for HVAC modes

## Installation

### HACS
1. Add this repository to HACS as a custom repository (Integration).
2. Install "PWM Climate Controller".
3. Restart Home Assistant.

### Manual
1. Copy `custom_components/pwm_climate` to `<config>/custom_components/`.
2. Restart Home Assistant.

## Configuration
This integration uses Config Flow in the UI. No YAML configuration is required.

Required inputs:
- Name
- Temperature sensor entity
- Output entity (`number` entity used for PWM)

Optional inputs:
- Humidity sensor entity
- Min/max temperature limits
- Temperature step
- PWM period (minutes)
- Preset target temperatures for HVAC modes

## Breaking Changes
- The integration domain changed and Home Assistant cannot automatically migrate config entries between domains.
- Remove the existing integration and add PWM Climate Controller again; entities will be recreated.

## Notes
- Humidity is displayed only; it does not affect control.
- Cooling and humidity control are not supported.
