from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .climate import KNXPIDClimate
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .const import DOMAIN

_LOGGER = logging.getLogger(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration via YAML  - HA requests"""
    _LOGGER.debug("async_setup called (YAML)")
    return True


# async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Set up integration from UI (ConfigEntry)."""
#     _LOGGER.info("KNX PID Climate – setup entry %s", entry.entry_id)
#
#     hass.data.setdefault(DOMAIN, {})
#     hass.data[DOMAIN][entry.entry_id] = {}
#
#     async def async_add_entities(add_entities: AddEntitiesCallback):
#         add_entities([
#             KNXPIDClimate(
#                 hass=hass,
#                 name="KNX PID Climate",
#             )
#         ])
#
#     hass.async_create_task(
#         hass.config_entries.async_forward_entry_setup(entry, "climate")
#     )
#
#     return True
#
#
# async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Unload integration."""
#     _LOGGER.info("KNX PID Climate – unload entry %s", entry.entry_id)
#
#     hass.data[DOMAIN].pop(entry.entry_id)
#     return True