"""Sanity checks on manifest.json and its relation to the changelog."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MANIFEST = json.loads((ROOT / "custom_components" / "venus300" / "manifest.json").read_text())

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def test_domain_matches_component_folder_name():
    assert MANIFEST["domain"] == "venus300"
    assert (ROOT / "custom_components" / MANIFEST["domain"]).is_dir()


def test_version_is_valid_semver():
    assert SEMVER_RE.match(MANIFEST["version"]), MANIFEST["version"]


def test_config_flow_enabled():
    assert MANIFEST["config_flow"] is True


def test_requirements_pin_pymodbus():
    assert any(r.startswith("pymodbus") for r in MANIFEST["requirements"])


def test_changelog_has_a_heading_for_the_current_version():
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert f"[{MANIFEST['version']}]" in changelog, (
        "bump the version in manifest.json and CHANGELOG.md together"
    )
