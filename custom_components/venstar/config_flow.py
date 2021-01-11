"""Config flow for venstar integration."""
import asyncio
from functools import partial
import logging
from urllib.parse import unquote, urlparse

import async_timeout
from getmac import get_mac_address
from venstarcolortouch import VenstarColorTouch
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

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
    VENSTAR_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, user_input):
    """Validate the user input allows us to connect."""
    timeout = 30

    addr = user_input.get(CONF_HOST)
    addr += ":" + user_input.get(CONF_PORT) if user_input.get(CONF_PORT) else ""
    protocol = "https" if user_input.get(CONF_SSL) else "http"

    api = VenstarColorTouch(
        addr=addr,
        timeout=timeout,
        user=user_input.get(CONF_USERNAME),
        password=user_input.get(CONF_PASSWORD),
        pin=user_input.get(CONF_PIN),
        proto=protocol,
    )

    async with async_timeout.timeout(timeout):
        if not await hass.async_add_executor_job(api.login):
            raise CannotConnect

    if not await hass.async_add_executor_job(api.update_info):
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {
        "title": getattr(api, VENSTAR_NAME),
    }


async def async_get_mac(hass: core.HomeAssistant, host):
    """Get the mac address of the thermostat."""
    try:
        mac_address = await hass.async_add_executor_job(
            partial(get_mac_address, **{"ip": host})
        )
        if not mac_address:
            mac_address = await hass.async_add_executor_job(
                partial(get_mac_address, **{"hostname": host})
            )
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.debug(f"Unable to get MAC address: {repr(err)}")
        mac_address = None

    if mac_address is not None:
        mac_address = format_mac(mac_address)
    return mac_address


async def async_construct_unique_id(
    hass: core.HomeAssistant, host=None, port=None, mac=None
):
    """Construct a unique identifier for the thermostat"""
    id = None

    if mac is None:
        mac = await async_get_mac(hass, host)

    if host is not None:
        id = "-".join(list(filter(None, [mac or host, port])))

    if id is None:
        _LOGGER.error(
            f"Unable to construct a unique identifier: host={host} port={port} mac={mac}"
        )

    return id


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Venstar."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HUMIDIFIER,
                    default=self.get_option(
                        CONF_HUMIDIFIER,
                        user_input=user_input,
                        default=DEFAULT_CONF_HUMIDIFIER,
                    ),
                ): bool,
                vol.Required(
                    CONF_SENSORS,
                    default=self.get_option(
                        CONF_SENSORS,
                        user_input=user_input,
                        default=DEFAULT_CONF_SENSORS,
                    ),
                ): bool,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.get_option(
                        CONF_SCAN_INTERVAL,
                        user_input=user_input,
                        default=DEFAULT_CONF_SCAN_INTERVAL,
                    ),
                ): vol.All(vol.Coerce(int), vol.Clamp(min=1)),
                vol.Required(
                    CONF_TIMEOUT,
                    default=self.get_option(
                        CONF_TIMEOUT,
                        user_input=user_input,
                        default=DEFAULT_CONF_TIMEOUT,
                    ),
                ): vol.All(vol.Coerce(int), vol.Clamp(min=1)),
            }
        )

        if self.get_option(
            CONF_SCAN_INTERVAL,
            user_input=user_input,
            default=DEFAULT_CONF_SCAN_INTERVAL,
        ) < self.get_option(
            CONF_TIMEOUT,
            user_input=user_input,
            default=DEFAULT_CONF_TIMEOUT,
        ):
            errors[CONF_TIMEOUT] = "timeout_high"

        if user_input is not None and len(errors) == 0:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )

    def get_option(self, id, user_input=None, default=None):
        """Return config option"""
        if user_input is None:
            user_input = {}

        return user_input.get(
            id,
            self.config_entry.options.get(id, self.config_entry.data.get(id, default)),
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Venstar."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self._discovery_data = {}
        self._unique_id = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=self.get_config(
                        CONF_HOST, user_input=user_input, default=""
                    ),
                ): str,
                vol.Optional(
                    CONF_PORT,
                    default=self.get_config(
                        CONF_PORT, user_input=user_input, default=DEFAULT_CONF_PORT
                    ),
                ): str,
                vol.Required(
                    CONF_SSL,
                    default=self.get_config(
                        CONF_SSL, user_input=user_input, default=DEFAULT_CONF_SSL
                    ),
                ): bool,
                vol.Optional(
                    CONF_USERNAME,
                    default=self.get_config(
                        CONF_USERNAME,
                        user_input=user_input,
                        default=DEFAULT_CONF_USERNAME,
                    ),
                ): str,
                vol.Optional(
                    CONF_PASSWORD,
                    default=self.get_config(
                        CONF_PASSWORD,
                        user_input=user_input,
                        default=DEFAULT_CONF_PASSWORD,
                    ),
                ): str,
                vol.Optional(
                    CONF_PIN,
                    default=self.get_config(
                        CONF_PIN, user_input=user_input, default=DEFAULT_CONF_PIN
                    ),
                ): str,
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except asyncio.TimeoutError:
            errors["base"] = "connect_timeout"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if user_input.get(CONF_MAC) is None:
                user_input[CONF_MAC] = await async_get_mac(
                    self.hass, user_input.get(CONF_HOST)
                )

            if self._unique_id is None:
                self._unique_id = await async_construct_unique_id(
                    self.hass,
                    host=user_input.get(CONF_HOST),
                    port=user_input.get(CONF_PORT),
                    mac=user_input.get(CONF_MAC),
                )
            await self.async_set_unique_id(self._unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_ssdp(self, info):
        """Handle discovery by SSDP."""
        ssdp_input = {}

        _LOGGER.debug("SSDP detected device")

        for key in info:
            _LOGGER.debug(f"SSDP {key} = {info[key]}")

        ssdp_input[CONF_SSL] = (
            True if urlparse(info[ssdp.ATTR_SSDP_LOCATION]).scheme == "https" else False
        )
        ssdp_input[CONF_HOST] = urlparse(info[ssdp.ATTR_SSDP_LOCATION]).hostname
        ssdp_input[CONF_PORT] = str(urlparse(info[ssdp.ATTR_SSDP_LOCATION]).port) or ""
        usn = info[ssdp.ATTR_SSDP_USN].split(":")
        ssdp_input[CONF_MAC] = format_mac(":".join(usn[2:8]))
        name = unquote(usn[9])

        _LOGGER.debug(
            f"SSDP data: ssl={ssdp_input.get(CONF_SSL)} host={ssdp_input.get(CONF_HOST)} port={ssdp_input.get(CONF_PORT)} mac={ssdp_input.get(CONF_MAC)} name={name}"
        )

        if self._unique_id is None:
            self._unique_id = await async_construct_unique_id(
                self.hass,
                host=ssdp_input.get(CONF_HOST),
                port=ssdp_input.get(CONF_PORT),
                mac=ssdp_input.get(CONF_MAC),
            )
        await self.async_set_unique_id(self._unique_id)
        self._abort_if_unique_id_configured()

        if name:
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            self.context.update({"title_placeholders": {"name": name}})

        self._discovery_data = ssdp_input

        return await self.async_step_user(ssdp_input)

    async def async_step_import(self, config_input):
        """Import Venstar config from configuration.yaml."""
        config_input.pop("platform", None)
        self._discovery_data = config_input
        return await self.async_step_user(config_input)

    def get_config(self, id, user_input=None, default=None):
        """Return config data"""
        if user_input is None:
            user_input = {}

        return user_input.get(
            id,
            self._discovery_data.get(id, default),
        )

    @property
    def unique_id(self):
        """Return the unique identifer of the entry."""
        return self._unique_id


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
