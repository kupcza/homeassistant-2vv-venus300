"""Every translation_key used by an entity platform must have a strings.json
entry, and strings.json must not declare keys nothing uses.
"""

import json
import re
from pathlib import Path

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "venus300"
TRANSLATED_LANGUAGES = ("en", "cs", "tr", "ro")


def _load_strings() -> dict:
    return json.loads((COMPONENT_DIR / "strings.json").read_text())


def _snake_case_literals(module_text: str) -> set[str]:
    return set(re.findall(r'"([a-z][a-z0-9_]+)"', module_text))


def _key_paths(data: object, prefix: str = "") -> set[str]:
    """Every dotted key path in a nested dict, for structural comparison."""
    if not isinstance(data, dict):
        return set()
    paths: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.add(path)
        paths |= _key_paths(value, path)
    return paths


def test_strings_json_and_translations_en_json_are_identical():
    strings = json.loads((COMPONENT_DIR / "strings.json").read_text())
    translations = json.loads((COMPONENT_DIR / "translations" / "en.json").read_text())
    assert strings == translations


def test_every_translation_file_has_the_same_keys_as_strings_json():
    reference = _key_paths(_load_strings())
    for language in TRANSLATED_LANGUAGES:
        path = COMPONENT_DIR / "translations" / f"{language}.json"
        assert path.is_file(), f"missing translations/{language}.json"
        keys = _key_paths(json.loads(path.read_text()))
        assert keys == reference, (
            f"{language}.json key mismatch: "
            f"missing={sorted(reference - keys)} extra={sorted(keys - reference)}"
        )


def test_switch_translation_keys_are_declared():
    declared = set(_load_strings()["entity"]["switch"])
    used = _snake_case_literals((COMPONENT_DIR / "switch.py").read_text())
    assert declared <= used, declared - used


def test_number_translation_keys_are_declared():
    declared = set(_load_strings()["entity"]["number"])
    used = _snake_case_literals((COMPONENT_DIR / "number.py").read_text())
    assert declared <= used, declared - used


def test_button_translation_keys_are_declared():
    declared = set(_load_strings()["entity"]["button"])
    used = _snake_case_literals((COMPONENT_DIR / "button.py").read_text())
    assert declared <= used, declared - used


def test_sensor_translation_keys_are_declared():
    declared = set(_load_strings()["entity"]["sensor"])
    used = _snake_case_literals((COMPONENT_DIR / "sensor.py").read_text())
    assert declared <= used, declared - used


def test_binary_sensor_translation_keys_match_bitfields_plus_computed_sensors():
    from custom_components.venus300 import bitfields

    # binary_sensor.py also declares a handful of entities that aren't
    # decoded from a status-word bit (see freecooling_conditions.py) --
    # listed explicitly here rather than pattern-matched from the module,
    # since there's no dataclass tuple to introspect for those.
    computed_sensors = {"freecooling_conditions_met"}

    declared = set(_load_strings()["entity"]["binary_sensor"])
    used = {spec.translation_key for spec in bitfields.ALL_BITS} | computed_sensors
    assert declared == used
