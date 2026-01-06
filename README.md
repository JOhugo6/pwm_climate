# HA
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
    custom_components.knx_pid_climate: debug
```