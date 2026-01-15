# PWM Climate Controller

PWM Climate Controller is a proportional PWM-based climate controller designed primarily for hydronic floor heating systems.

## Control Algorithm
This integration uses proportional (P) control with PWM output.
It does NOT implement a full PID controller.

## Breaking Changes
This release renames the integration domain to `pwm_climate`.
To preserve existing config entries and entity IDs, update Home Assistant storage before restarting:
1. Stop Home Assistant.
2. Back up the `.storage` directory.
3. In `.storage/core.config_entries`, locate entries that contain `temperature_entity`, `output_entity`, and `pwm_period`, then set their `domain` to `pwm_climate`.
4. In `.storage/core.entity_registry`, locate entities with the same `config_entry_id` and set their `platform` to `pwm_climate`.
5. Start Home Assistant.

## Repository Notes
Home Assistant integrations

## Installation

### Download Python
https://www.python.org/downloads/windows/
- Before download check the latest supported version for Home Assistant.

### Create venv

```
cmd:
cd C:\vyvoj\h6system\git\HA
py -m venv .venv
```

### Activation venv

```
cmd:
.venv\Scripts\activate
```
![img.png](img.png)

### Get Home Assistant

https://github.com/home-assistant/core.git

![img_1.png](img_1.png)
![img_2.png](img_2.png)

## Enable DEBUG LOGGING in HA

```
logger:
default: warning
logs:
    custom_components.pwm_climate: debug
```
