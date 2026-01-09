import logging

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from .const import DOMAIN

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
        self._attr_current_temperature = 20.0
        self._attr_target_temperature = 21.0

        _LOGGER.debug("KNXPIDClimate entity INIT: %s", name)

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._attr_target_temperature = float(temperature)

        _LOGGER.info(
            "KNX PID: Target temperature set to %.1f °C",
            self._attr_target_temperature,
        )

        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode) -> None:
        self._attr_hvac_mode = hvac_mode

        _LOGGER.info(
            "KNX PID: HVAC mode changed to %s",
            hvac_mode,
        )

        self.async_write_ha_state()
