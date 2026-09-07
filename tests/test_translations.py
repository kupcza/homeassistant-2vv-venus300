"""Every translation_key used by an entity platform must have a strings.json
entry, and strings.json must not declare keys nothing uses.
"""

import json
import re
from pathlib import Path

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "venus300"


def _load_strings() -> dict:
    return json.loads((COMPONENT_DIR / "strings.json").read_text())


def _snake_case_literals(module_text: str) -> set[str]:
    return set(re.findall(r'"([a-z][a-z0-9_]+)"', module_text))


def test_strings_json_and_translations_en_json_are_identical():
    strings = json.loads((COMPONENT_DIR / "strings.json").read_text())
    translations = json.loads((COMPONENT_DIR / "translations" / "en.json").read_text())
    assert strings == translations


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


def test_binary_sensor_translation_keys_match_bitfields_exactly():
    from custom_components.venus300 import bitfields

    declared = set(_load_strings()["entity"]["binary_sensor"])
    used = {spec.translation_key for spec in bitfields.ALL_BITS}
    assert declared == used
