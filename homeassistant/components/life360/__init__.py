"""Life360 integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import CONF_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PREFIX, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CIRCLES,
    CONF_DRIVING_SPEED,
    CONF_ERROR_THRESHOLD,
    CONF_MAX_GPS_ACCURACY,
    CONF_MAX_UPDATE_WAIT,
    CONF_MEMBERS,
    CONF_SHOW_AS_STATE,
    CONF_WARNING_THRESHOLD,
    DEFAULT_OPTIONS,
    DOMAIN,
    LOGGER,
    SHOW_DRIVING,
    SHOW_MOVING,
)
from .coordinator import Life360DataUpdateCoordinator

PLATFORMS = [Platform.DEVICE_TRACKER]

CONF_ACCOUNTS = "accounts"

SHOW_AS_STATE_OPTS = [SHOW_DRIVING, SHOW_MOVING]


def _show_as_state(opts: list[str]) -> list[str]:
    """Warn about unsupported show_as_state options and remove from config."""
    if SHOW_MOVING in opts:
        LOGGER.warning(
            "%s is no longer supported as an option for %s",
            SHOW_MOVING,
            CONF_SHOW_AS_STATE,
        )
    return [value for value in opts if value != SHOW_MOVING]


def _unsupported(unsupported: set[str]) -> Callable[[dict], dict]:
    """Warn about unsupported options and remove from config."""

    def validator(config: dict) -> dict:
        if unsupported_keys := unsupported & set(config):
            LOGGER.warning(
                "The following options are no longer supported: %s",
                ", ".join(sorted(unsupported_keys)),
            )
        return {k: v for k, v in config.items() if k not in unsupported}

    return validator


LIFE360_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_ACCOUNTS): vol.All(cv.ensure_list, [{}]),
            vol.Optional(CONF_CIRCLES): {},
            vol.Optional(CONF_DRIVING_SPEED): vol.Coerce(float),
            vol.Optional(CONF_ERROR_THRESHOLD): vol.Coerce(int),
            vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
            vol.Optional(CONF_MAX_UPDATE_WAIT): cv.time_period,
            vol.Optional(CONF_MEMBERS): {},
            vol.Optional(CONF_PREFIX): vol.Any(None, cv.string),
            vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
            vol.Optional(CONF_SHOW_AS_STATE, default=[]): vol.All(
                cv.ensure_list, [vol.In(SHOW_AS_STATE_OPTS)], _show_as_state
            ),
            vol.Optional(CONF_WARNING_THRESHOLD): vol.Coerce(int),
        }
    ),
    _unsupported(
        {
            CONF_ACCOUNTS,
            CONF_CIRCLES,
            CONF_ERROR_THRESHOLD,
            CONF_MAX_UPDATE_WAIT,
            CONF_MEMBERS,
            CONF_PREFIX,
            CONF_SCAN_INTERVAL,
            CONF_WARNING_THRESHOLD,
        }
    ),
)
CONFIG_SCHEMA = vol.Schema(
    vol.All({DOMAIN: LIFE360_SCHEMA}, cv.removed(DOMAIN, raise_if_present=False)),
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class IntegData:
    """Integration data."""

    cfg_options: dict[str, Any] | None = None
    # ConfigEntry.unique_id: Life360DataUpdateCoordinator
    coordinators: dict[str, Life360DataUpdateCoordinator] = field(
        init=False, default_factory=dict
    )
    # member_id: ConfigEntry.unique_id
    tracked_members: dict[str, str] = field(init=False, default_factory=dict)
    logged_circles: list[str] = field(init=False, default_factory=list)
    logged_places: list[str] = field(init=False, default_factory=list)

    def __post_init__(self):
        """Finish initialization of cfg_options."""
        self.cfg_options = self.cfg_options or {}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration."""
    hass.data.setdefault(DOMAIN, IntegData(config.get(DOMAIN)))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    hass.data.setdefault(DOMAIN, IntegData())

    # Check if this entry was created when this was a "legacy" tracker. If it was,
    # update with missing data.
    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=entry.data[CONF_USERNAME].lower(),
            options=DEFAULT_OPTIONS | hass.data[DOMAIN].cfg_options,
        )

    coordinator = Life360DataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN].coordinators[entry.entry_id] = coordinator

    # Set up components for our platforms.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    del hass.data[DOMAIN].coordinators[entry.entry_id]

    # Unload components for our platforms.
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
