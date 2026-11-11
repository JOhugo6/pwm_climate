from __future__ import annotations

import sys
import types
from enum import IntFlag
from typing import Any

try:
    import voluptuous as vol  # type: ignore[no-redef]
except ModuleNotFoundError:
    vol = types.ModuleType("voluptuous")

    class _Marker:
        def __init__(self, kind: str, key: Any, default: Any = None, description: Any = None) -> None:
            self.kind = kind
            self.key = key
            self.default = default
            self.description = description

        def __hash__(self) -> int:
            return hash((self.kind, self.key, self.default))

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, _Marker):
                return False
            return (
                self.kind == other.kind
                and self.key == other.key
                and self.default == other.default
            )

    def Required(key: Any, default: Any = None, description: Any = None) -> _Marker:
        return _Marker("required", key, default, description)

    def Optional(key: Any, default: Any = None, description: Any = None) -> _Marker:
        return _Marker("optional", key, default, description)

    def Coerce(type_: Any) -> Any:
        return type_

    class Schema:
        def __init__(self, schema: Any) -> None:
            self.schema = schema

    vol.Required = Required
    vol.Optional = Optional
    vol.Coerce = Coerce
    vol.Schema = Schema
    sys.modules["voluptuous"] = vol


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
    sensor_module = types.ModuleType("homeassistant.components.sensor")

    const_module = types.ModuleType("homeassistant.const")
    const_module.CONF_NAME = "name"
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

    class _FlowBase:
        """Minimal base class for config and options flows."""

        def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: Any,
            errors: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": {} if errors is None else errors,
            }

    class ConfigFlow(_FlowBase):
        """Minimal ConfigFlow stub for module imports."""

        def __init_subclass__(cls, **kwargs: Any) -> None:
            cls.domain = kwargs.pop("domain", None)
            super().__init_subclass__()

    class OptionsFlow(_FlowBase):
        """Minimal OptionsFlow stub for module imports."""

    config_entries_module.ConfigFlow = ConfigFlow
    config_entries_module.OptionsFlow = OptionsFlow

    helpers_module = types.ModuleType("homeassistant.helpers")
    helpers_module.__path__ = []  # type: ignore[attr-defined]

    entity_module = types.ModuleType("homeassistant.helpers.entity")
    entity_platform_module = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform_module.AddEntitiesCallback = Any

    entity_registry_module = types.ModuleType("homeassistant.helpers.entity_registry")

    event_module = types.ModuleType("homeassistant.helpers.event")

    def async_track_state_change_event(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return lambda: None

    event_module.async_track_state_change_event = async_track_state_change_event

    def async_get(hass: Any) -> Any:
        registry = getattr(hass, "entity_registry", None)
        if registry is None:
            registry = types.SimpleNamespace(entities={})
            setattr(hass, "entity_registry", registry)
        return registry

    entity_registry_module.async_get = async_get

    class DeviceInfo:
        """Minimal DeviceInfo stub for entity metadata tests."""

        def __init__(
            self,
            *,
            identifiers: set[tuple[str, str]] | None = None,
            manufacturer: str | None = None,
            model: str | None = None,
            name: str | None = None,
        ) -> None:
            self.identifiers = set() if identifiers is None else identifiers
            self.manufacturer = manufacturer
            self.model = model
            self.name = name

    selector_module = types.ModuleType("homeassistant.helpers.selector")

    class _SelectorConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class _Selector:
        def __init__(self, config: Any) -> None:
            self.config = config

        def __call__(self, value: Any) -> Any:
            # Real Voluptuous compiles selectors as callable validators. These
            # remain HA stubs; tests of omission/defaults use real Voluptuous.
            return value

    class EntitySelectorConfig(_SelectorConfig):
        pass

    class NumberSelectorConfig(_SelectorConfig):
        pass

    class SelectSelectorConfig(_SelectorConfig):
        pass

    class EntitySelector(_Selector):
        pass

    class NumberSelector(_Selector):
        pass

    class SelectSelector(_Selector):
        pass

    class NumberSelectorMode:
        SLIDER = "slider"
        BOX = "box"

    class SelectSelectorMode:
        DROPDOWN = "dropdown"

    selector_module.EntitySelector = EntitySelector
    selector_module.EntitySelectorConfig = EntitySelectorConfig
    selector_module.NumberSelector = NumberSelector
    selector_module.NumberSelectorConfig = NumberSelectorConfig
    selector_module.NumberSelectorMode = NumberSelectorMode
    selector_module.SelectSelector = SelectSelector
    selector_module.SelectSelectorConfig = SelectSelectorConfig
    selector_module.SelectSelectorMode = SelectSelectorMode

    class SensorDeviceClass:
        TEMPERATURE = "temperature"

    sensor_module.SensorDeviceClass = SensorDeviceClass

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

        @property
        def device_info(self) -> Any:
            return getattr(self, "_attr_device_info", None)

        @property
        def unique_id(self) -> Any:
            return getattr(self, "_attr_unique_id", None)

    class ClimateEntityFeature(IntFlag):
        TARGET_TEMPERATURE = 1
        TURN_ON = 2
        TURN_OFF = 4
        PRESET_MODE = 8

    climate_module.ClimateEntity = ClimateEntity
    climate_module.ClimateEntityFeature = ClimateEntityFeature
    climate_const_module.ClimateEntityFeature = ClimateEntityFeature
    climate_const_module.ClimateEntity = ClimateEntity
    sensor_module.SensorEntity = object

    homeassistant_module.components = components_module
    homeassistant_module.const = const_module
    homeassistant_module.core = core_module
    homeassistant_module.exceptions = exceptions_module
    homeassistant_module.config_entries = config_entries_module
    homeassistant_module.helpers = helpers_module

    components_module.climate = climate_module
    components_module.sensor = sensor_module
    climate_module.const = climate_const_module
    entity_module.DeviceInfo = DeviceInfo
    helpers_module.entity_platform = entity_platform_module
    helpers_module.entity = entity_module
    helpers_module.event = event_module
    helpers_module.entity_registry = entity_registry_module
    helpers_module.selector = selector_module
    helpers_module.restore_state = restore_state_module

    sys.modules["homeassistant"] = homeassistant_module
    sys.modules["homeassistant.components"] = components_module
    sys.modules["homeassistant.components.climate"] = climate_module
    sys.modules["homeassistant.components.climate.const"] = climate_const_module
    sys.modules["homeassistant.components.sensor"] = sensor_module
    sys.modules["homeassistant.const"] = const_module
    sys.modules["homeassistant.core"] = core_module
    sys.modules["homeassistant.exceptions"] = exceptions_module
    sys.modules["homeassistant.config_entries"] = config_entries_module
    sys.modules["homeassistant.helpers"] = helpers_module
    sys.modules["homeassistant.helpers.entity"] = entity_module
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform_module
    sys.modules["homeassistant.helpers.event"] = event_module
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry_module
    sys.modules["homeassistant.helpers.selector"] = selector_module
    sys.modules["homeassistant.helpers.restore_state"] = restore_state_module


_install_homeassistant_stubs()
