from __future__ import annotations

import sys
import types
from enum import IntFlag
from typing import Any


def _install_homeassistant_stubs() -> None:
    if "homeassistant" in sys.modules:
        return

    homeassistant_module = types.ModuleType("homeassistant")
    homeassistant_module.__path__ = []  # type: ignore[attr-defined]

    components_module = types.ModuleType("homeassistant.components")
    components_module.__path__ = []  # type: ignore[attr-defined]

    climate_module = types.ModuleType("homeassistant.components.climate")
    climate_module.__path__ = []  # type: ignore[attr-defined]

    climate_const_module = types.ModuleType("homeassistant.components.climate.const")

    const_module = types.ModuleType("homeassistant.const")
    const_module.ATTR_TEMPERATURE = "temperature"
    const_module.STATE_UNAVAILABLE = "unavailable"
    const_module.STATE_UNKNOWN = "unknown"

    class UnitOfTemperature:
        CELSIUS = "C"

    const_module.UnitOfTemperature = UnitOfTemperature

    core_module = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        """Minimal Home Assistant stub for module imports."""

        def __init__(self) -> None:
            self.data: dict[str, Any] = {}
            self.config_entries = types.SimpleNamespace(
                async_forward_entry_setups=lambda *args, **kwargs: None
            )

        def async_create_task(self, coro: Any) -> Any:
            return coro

    def callback(func: Any) -> Any:
        return func

    class Event:
        def __init__(self, data: dict[str, Any] | None = None) -> None:
            self.data = {} if data is None else data

    class State:
        def __init__(self, state: Any = None) -> None:
            self.state = state

    core_module.HomeAssistant = HomeAssistant
    core_module.Event = Event
    core_module.State = State
    core_module.callback = callback

    exceptions_module = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        """Minimal HomeAssistantError stub for module imports."""

    exceptions_module.HomeAssistantError = HomeAssistantError

    config_entries_module = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        """Minimal ConfigEntry stub for integration package imports."""

        def __init__(
            self,
            entry_id: str = "entry-id",
            data: dict[str, Any] | None = None,
            options: dict[str, Any] | None = None,
            title: str = "PWM Climate Controller",
        ) -> None:
            self.entry_id = entry_id
            self.data = {} if data is None else data
            self.options = {} if options is None else options
            self.title = title

    config_entries_module.ConfigEntry = ConfigEntry

    helpers_module = types.ModuleType("homeassistant.helpers")
    helpers_module.__path__ = []  # type: ignore[attr-defined]

    entity_platform_module = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform_module.AddEntitiesCallback = Any

    event_module = types.ModuleType("homeassistant.helpers.event")

    def async_track_state_change_event(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return lambda: None

    event_module.async_track_state_change_event = async_track_state_change_event

    restore_state_module = types.ModuleType("homeassistant.helpers.restore_state")

    class RestoreEntity:
        """Minimal RestoreEntity stub for module imports."""

    restore_state_module.RestoreEntity = RestoreEntity

    climate_const_module.ATTR_PRESET_MODE = "preset_mode"

    class HVACMode(str):
        OFF = "off"
        HEAT = "heat"

    climate_const_module.HVACMode = HVACMode

    class ClimateEntity:
        """Minimal ClimateEntity stub for module imports."""

    class ClimateEntityFeature(IntFlag):
        TARGET_TEMPERATURE = 1
        TURN_ON = 2
        TURN_OFF = 4
        PRESET_MODE = 8

    climate_module.ClimateEntity = ClimateEntity
    climate_module.ClimateEntityFeature = ClimateEntityFeature
    climate_const_module.ClimateEntityFeature = ClimateEntityFeature
    climate_const_module.ClimateEntity = ClimateEntity

    homeassistant_module.components = components_module
    homeassistant_module.const = const_module
    homeassistant_module.core = core_module
    homeassistant_module.exceptions = exceptions_module
    homeassistant_module.config_entries = config_entries_module
    homeassistant_module.helpers = helpers_module

    components_module.climate = climate_module
    climate_module.const = climate_const_module
    helpers_module.entity_platform = entity_platform_module
    helpers_module.event = event_module
    helpers_module.restore_state = restore_state_module

    sys.modules["homeassistant"] = homeassistant_module
    sys.modules["homeassistant.components"] = components_module
    sys.modules["homeassistant.components.climate"] = climate_module
    sys.modules["homeassistant.components.climate.const"] = climate_const_module
    sys.modules["homeassistant.const"] = const_module
    sys.modules["homeassistant.core"] = core_module
    sys.modules["homeassistant.exceptions"] = exceptions_module
    sys.modules["homeassistant.config_entries"] = config_entries_module
    sys.modules["homeassistant.helpers"] = helpers_module
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform_module
    sys.modules["homeassistant.helpers.event"] = event_module
    sys.modules["homeassistant.helpers.restore_state"] = restore_state_module


_install_homeassistant_stubs()
