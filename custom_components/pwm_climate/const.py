# Global constants

DOMAIN = "pwm_climate"
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
CONF_DEFAULT_PRESET = "default_preset"
CONF_PRESET_AUTO_TEMPERATURE = "hvac_auto_temperature"
CONF_PRESET_COMFORT_TEMPERATURE = "hvac_comfort_temperature"
CONF_PRESET_READY_TEMPERATURE = "hvac_standby_temperature"
CONF_PRESET_ECO_TEMPERATURE = "hvac_economy_temperature"
CONF_PRESET_BUILDING_PROTECTION_TEMPERATURE = "hvac_building_protection_temperature"

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

PRESET_DEFAULT_TEMPERATURES: dict[int, float] = {
    0: 22.0,  # Auto
    1: 24.0,  # Komfort
    2: 22.0,  # Připraveno
    3: 21.0,  # ECO
    4: 8.0,   # Ochrana budovy
}

PRESET_LABELS: dict[int, str] = {
    0: "Auto",
    1: "Komfort",
    2: "Připraveno",
    3: "ECO",
    4: "Ochrana budovy",
}

PRESET_TEMPERATURE_KEYS: dict[int, str] = {
    0: CONF_PRESET_AUTO_TEMPERATURE,
    1: CONF_PRESET_COMFORT_TEMPERATURE,
    2: CONF_PRESET_READY_TEMPERATURE,
    3: CONF_PRESET_ECO_TEMPERATURE,
    4: CONF_PRESET_BUILDING_PROTECTION_TEMPERATURE,
}

PRESET_NAMES: list[str] = list(PRESET_LABELS.values())
DEFAULT_PRESET = PRESET_LABELS[0]
PRESET_MANUAL = "manual"
