"""Constants for the 2VV Venus 300 integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "venus300"
MANUFACTURER = "2VV"
MODEL = "Venus 300 (AirGenio)"

CONF_SLAVE_ID = "slave_id"

DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 1
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_BOOST_TIMER_MINUTES = 5
