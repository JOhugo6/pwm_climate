# Global constants

DOMAIN = "pid_climate"
LOGGER_NAME = DOMAIN

# ---- Config keys (ConfigEntry.data) ----
CONF_NAME = "name"

# ─────────────────────────────────────────────
# Config keys
# ─────────────────────────────────────────────

CONF_TEMPERATURE_ENTITY = "temperature_entity"
CONF_OUTPUT_ENTITY = "output_entity"
CONF_HUMIDITY_ENTITY = "humidity_entity"

CONF_TEMPERATURE_STEP = "temperature_step"
CONF_MIN_TEMPERATURE = "min_temperature"
CONF_MAX_TEMPERATURE = "max_temperature"
CONF_PWM_PERIOD = "pwm_period"

CONF_HVAC_MODES = "hvac_modes"

# ─────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────

DEFAULT_TEMPERATURE_STEP = 0.1
DEFAULT_MIN_TEMPERATURE = 20.0
DEFAULT_MAX_TEMPERATURE = 28.0
DEFAULT_PWM_PERIOD = 15  # minutes

# ─────────────────────────────────────────────
# HVAC modes – KNX DPT 20.102
# ─────────────────────────────────────────────
# key = KNX value
# value = default target temperature (°C)

HVAC_MODE_DEFAULT_TEMPERATURES: dict[int, float] = {
    0: 22.0,  # Auto
    1: 24.0,  # Comfort
    2: 22.0,  # Standby
    3: 21.0,  # Economy
    4: 8.0,   # Building protection
}

HVAC_MODE_LABELS: dict[int, str] = {
    0: "Auto",
    1: "Comfort",
    2: "Standby",
    3: "Economy",
    4: "Building protection",
}
