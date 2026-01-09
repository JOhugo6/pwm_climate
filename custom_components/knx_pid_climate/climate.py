import logging

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from .const import DOMAIN
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(DOMAIN)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.info("KNX_PID_CLIMATE async_setup_platform CALLED")

    async_add_entities([
        KNXPIDClimate(
            name=config.get("name", "KNX PID Test")
        )
    ])


class KNXPIDClimate(ClimateEntity):
    """Minimal valid ClimateEntity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(self, name: str):
        self._attr_name = name
        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_current_temperature = None
        self._attr_target_temperature = 21.0

        self._temperature_sensor_entity_id = "sensor.teplota_obyvak_futura"
        self._unsub_temp = None

        _LOGGER.debug("KNXPIDClimate entity INIT: %s", name)

    async def async_set_temperature(self, **kwargs) -> None:
        """Handle target temperature change."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            _LOGGER.debug("async_set_temperature called without temperature")
            return

        self._attr_target_temperature = float(temperature)

        _LOGGER.info(
            "KNX PID Climate setpoint changed to %.1f °C",
            self._attr_target_temperature,
        )

        # zatím jen přepíšeme stav entity
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode) -> None:
        self._attr_hvac_mode = hvac_mode

        _LOGGER.info(
            "KNX PID: HVAC mode changed to %s",
            hvac_mode,
        )

        self.async_write_ha_state()

    @callback
    def _handle_temperature_change(self, event):
        new_state = event.data.get("new_state")

        if new_state is None or new_state.state in (None, "unknown", "unavailable"):
            return

        try:
            self._attr_current_temperature = float(new_state.state)
            _LOGGER.info(
                "KNX PID Climate: temperature updated to %.1f °C",
                self._attr_current_temperature,
            )
            self.async_write_ha_state()
        except ValueError:
            _LOGGER.warning("Invalid temperature value: %s", new_state.state)

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to HA."""
        _LOGGER.info("KNX PID Climate added to HA: %s", self.name)

        # Přihlášení k poslouchání změn teplotního senzoru
        self._unsub_temp = async_track_state_change_event(
            self.hass,
            [self._temperature_sensor_entity_id],
            self._handle_temperature_change,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_temp:
            self._unsub_temp()
            self._unsub_temp = None
