from __future__ import annotations

import sys
import types
from typing import Any


def _install_homeassistant_stubs() -> None:
    if "homeassistant" in sys.modules:
        return

    homeassistant_module = types.ModuleType("homeassistant")
    homeassistant_module.__path__ = []  # type: ignore[attr-defined]

    const_module = types.ModuleType("homeassistant.const")
    const_module.ATTR_TEMPERATURE = "temperature"

    core_module = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        """Minimal Home Assistant stub for module imports."""

    core_module.HomeAssistant = HomeAssistant

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
        ) -> None:
            self.entry_id = entry_id
            self.data = {} if data is None else data

    config_entries_module.ConfigEntry = ConfigEntry

    sys.modules["homeassistant"] = homeassistant_module
    sys.modules["homeassistant.const"] = const_module
    sys.modules["homeassistant.core"] = core_module
    sys.modules["homeassistant.exceptions"] = exceptions_module
    sys.modules["homeassistant.config_entries"] = config_entries_module


_install_homeassistant_stubs()
