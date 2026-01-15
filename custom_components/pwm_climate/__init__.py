"""PWM Climate Controller integration."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .climate import PWMClimateController
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .const import DOMAIN, LOGGER_NAME

_LOGGER = logging.getLogger(LOGGER_NAME)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry,["climate"],)
    return True
