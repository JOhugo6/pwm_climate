from __future__ import annotations

from custom_components.pwm_climate.const import (
    CONF_HVAC_MODES,
    PRESET_DEFAULT_TEMPERATURES,
    PRESET_LABELS,
    PRESET_TEMPERATURE_KEYS,
)
from custom_components.pwm_climate.preset_helpers import (
    _apply_flat_preset_temperatures,
    _merge_preset_temperatures,
    resolve_preset_temperatures,
)


def test_apply_flat_preset_temperatures_preserves_known_keys_and_ignores_invalid_values() -> None:
    base = dict(PRESET_DEFAULT_TEMPERATURES)

    result = _apply_flat_preset_temperatures(
        base,
        {
            PRESET_TEMPERATURE_KEYS[0]: "23,5",
            PRESET_TEMPERATURE_KEYS[2]: "not-a-number",
            "unknown_key": 99,
        },
    )

    assert result is base
    assert result[0] == 23.5
    assert result[1] == PRESET_DEFAULT_TEMPERATURES[1]
    assert result[2] == PRESET_DEFAULT_TEMPERATURES[2]


def test_apply_flat_preset_temperatures_ignores_non_mapping_source() -> None:
    base = dict(PRESET_DEFAULT_TEMPERATURES)

    result = _apply_flat_preset_temperatures(base, ["not", "a", "mapping"])

    assert result == PRESET_DEFAULT_TEMPERATURES


def test_merge_preset_temperatures_accepts_labels_and_numeric_like_ids() -> None:
    base = dict(PRESET_DEFAULT_TEMPERATURES)

    result = _merge_preset_temperatures(
        base,
        {
            PRESET_LABELS[1]: "26.5",
            "3": "19.0",
            "bogus": 99,
            "99": 77.0,
        },
    )

    assert result is base
    assert result[1] == 26.5
    assert result[3] == 19.0
    assert result[0] == PRESET_DEFAULT_TEMPERATURES[0]
    assert result[4] == PRESET_DEFAULT_TEMPERATURES[4]


def test_merge_preset_temperatures_ignores_non_mapping_source() -> None:
    base = dict(PRESET_DEFAULT_TEMPERATURES)

    result = _merge_preset_temperatures(base, ["not", "a", "mapping"])

    assert result == PRESET_DEFAULT_TEMPERATURES


def test_resolve_preset_temperatures_returns_defaults_for_missing_inputs() -> None:
    assert resolve_preset_temperatures(None, None) == PRESET_DEFAULT_TEMPERATURES


def test_resolve_preset_temperatures_preserves_overlay_order_for_flat_and_nested_sources() -> None:
    temperatures = resolve_preset_temperatures(
        {
            PRESET_TEMPERATURE_KEYS[0]: "23.0",
            CONF_HVAC_MODES: {PRESET_LABELS[1]: "25.0"},
        },
        {
            PRESET_TEMPERATURE_KEYS[0]: "24.0",
            CONF_HVAC_MODES: {"1": "26.0"},
        },
    )

    assert temperatures[0] == 24.0
    assert temperatures[1] == 26.0
    assert temperatures[2] == PRESET_DEFAULT_TEMPERATURES[2]
    assert temperatures[3] == PRESET_DEFAULT_TEMPERATURES[3]
