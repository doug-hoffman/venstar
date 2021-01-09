"""The venstar integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from venstarcolortouch import VenstarColorTouch
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HUMIDIFIER,
    DEFAULT_CONF_HUMIDIFIER,
    DEFAULT_CONF_PASSWORD,
    DEFAULT_CONF_PIN,
    DEFAULT_CONF_PORT,
    DEFAULT_CONF_SCAN_INTERVAL,
    DEFAULT_CONF_SENSORS,
    DEFAULT_CONF_SSL,
    DEFAULT_CONF_TIMEOUT,
    DEFAULT_CONF_USERNAME,
    DOMAIN,
    ENTRY_API,
    ENTRY_CONNECTION_STATE,
    ENTRY_COORDINATOR,
    ENTRY_UNDO_UPDATE_LISTENER,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["climate", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Venstar component."""

    # venstarcolortouch is unnecessarily noisy at default levels
    if logging.getLogger("venstarcolortouch").level is logging.NOTSET:
        logging.getLogger("venstarcolortouch").setLevel(logging.CRITICAL)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Venstar from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    protocol = "https" if entry.data.get(CONF_SSL, DEFAULT_CONF_SSL) else "http"
    addr = entry.data.get(CONF_HOST)
    addr += (
        ":" + entry.data.get(CONF_PORT)
        if entry.data.get(CONF_PORT, DEFAULT_CONF_PORT)
        else ""
    )
    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_CONF_SCAN_INTERVAL)
    timeout = entry.options.get(
        CONF_TIMEOUT, entry.data.get(CONF_TIMEOUT, DEFAULT_CONF_TIMEOUT)
    )  # check data for migrated configuration.yaml entries

    api = VenstarColorTouch(
        addr=addr,
        timeout=timeout,
        user=entry.data.get(CONF_USERNAME, DEFAULT_CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD, DEFAULT_CONF_PASSWORD),
        pin=entry.data.get(CONF_PIN, DEFAULT_CONF_PIN),
        proto=protocol,
    )

    if not await hass.async_add_executor_job(api.login):
        _LOGGER.error(
            f"Unable to connect to {entry.title} with protocol={protocol} address={addr} timeout={timeout}"
        )
        raise ConfigEntryNotReady

    _LOGGER.info(
        f"{entry.title} initialized with protocol={protocol} address={addr} interval={interval} timeout={timeout}"
    )

    undo_listener = entry.add_update_listener(update_listener)

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(timeout):
                info_success = await hass.async_add_executor_job(api.update_info)
                sensor_success = await hass.async_add_executor_job(api.update_sensors)
            if not info_success or not sensor_success:
                hass.data[DOMAIN][entry.entry_id][ENTRY_CONNECTION_STATE] = False
                raise UpdateFailed("unable to update data")
        except asyncio.TimeoutError:
            hass.data[DOMAIN][entry.entry_id][ENTRY_CONNECTION_STATE] = False
            raise UpdateFailed("timeout occurred while updating data")
        except Exception as err:  # pylint: disable=broad-except
            hass.data[DOMAIN][entry.entry_id][ENTRY_CONNECTION_STATE] = False
            raise UpdateFailed(repr(err))
        hass.data[DOMAIN][entry.entry_id][ENTRY_CONNECTION_STATE] = True

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=entry.title,
        update_method=async_update_data,
        update_interval=timedelta(seconds=interval),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_API: api,
        ENTRY_CONNECTION_STATE: False,
        ENTRY_COORDINATOR: coordinator,
        ENTRY_UNDO_UPDATE_LISTENER: undo_listener,
    }

    await coordinator.async_refresh()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][entry.entry_id][ENTRY_UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
