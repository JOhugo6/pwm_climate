"""PWM Climate Controller integration."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(DOMAIN)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Ensure integration storage exists under hass.data and keep per-entry config data.
    # This makes the entry data accessible to platforms loaded via forward_entry_setups.
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward the config entry setup to the climate platform only.
    # Home Assistant will call the climate platform's async_setup_entry next.
    await hass.config_entries.async_forward_entry_setups(entry,["climate"],)
    return True
