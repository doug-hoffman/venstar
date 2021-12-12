"""Support for Venstar WiFi Thermostats."""
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_ON,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_START,
    PRECISION_HALVES,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_FAN_STATE,
    ATTR_HVAC_STATE,
    CONF_HUMIDIFIER,
    DEFAULT_CONF_HUMIDIFIER,
    DEFAULT_CONF_PASSWORD,
    DEFAULT_CONF_PIN,
    DEFAULT_CONF_SSL,
    DEFAULT_CONF_TIMEOUT,
    DEFAULT_CONF_USERNAME,
    DOMAIN,
    ENTRY_API,
    ENTRY_CONNECTION_STATE,
    ENTRY_COORDINATOR,
    HOLD_MODE_TEMPERATURE,
    MODE_MAP,
    VALID_FAN_STATES,
    VALID_PRESET_MODES,
    VALID_THERMOSTAT_MODES,
    VENSTAR_AWAY,
    VENSTAR_AWAY_AWAY,
    VENSTAR_AWAY_HOME,
    VENSTAR_COOLTEMP,
    VENSTAR_FAN,
    VENSTAR_FAN_AUTO,
    VENSTAR_FAN_ON,
    VENSTAR_FANSTATE,
    VENSTAR_HEATTEMP,
    VENSTAR_HUM_ACTIVE,
    VENSTAR_HUM_SETPOINT,
    VENSTAR_MODE,
    VENSTAR_MODE_AUTO,
    VENSTAR_MODE_COOL,
    VENSTAR_MODE_HEAT,
    VENSTAR_MODE_OFF,
    VENSTAR_MODEL,
    VENSTAR_NAME,
    VENSTAR_SCHEDULE,
    VENSTAR_SCHEDULE_DISABLED,
    VENSTAR_SCHEDULE_ENABLED,
    VENSTAR_STATE,
    VENSTAR_STATE_COOLING,
    VENSTAR_STATE_HEATING,
    VENSTAR_STATE_IDLE,
    VENSTAR_TEMPUNITS,
    VENSTAR_TEMPUNITS_F,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HUMIDIFIER, default=True): cv.boolean,
        vol.Optional(CONF_SSL, default=DEFAULT_CONF_SSL): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_CONF_TIMEOUT): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_USERNAME, default=DEFAULT_CONF_USERNAME): cv.string,
        vol.Optional(CONF_PIN, default=DEFAULT_CONF_PIN): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Venstar thermostat from configuration.yaml."""

    @callback
    def schedule_import(_):
        """Schedule delayed import after HA is fully started."""
        async_call_later(hass, 10, do_import)

    @callback
    def do_import(_):
        """Process YAML import."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
            )
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, schedule_import)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Venstar thermostat."""

    async_add_entities(
        [
            VenstarThermostat(
                hass.data[DOMAIN][entry.entry_id][ENTRY_COORDINATOR],
                hass.data[DOMAIN][entry.entry_id][ENTRY_API],
                entry,
            )
        ],
        True,
    )


class VenstarThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a Venstar thermostat."""

    def __init__(self, coordinator, api, config_entry):
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._client = api
        self._config_entry = config_entry

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE

        if getattr(self._client, VENSTAR_MODE) == VENSTAR_MODE_AUTO:
            features |= SUPPORT_TARGET_TEMPERATURE_RANGE

        if (
            self._config_entry.options.get(
                CONF_HUMIDIFIER,
                self._config_entry.data.get(CONF_HUMIDIFIER, DEFAULT_CONF_HUMIDIFIER),
            )
            and hasattr(self._client, VENSTAR_HUM_ACTIVE)
        ):
            features |= SUPPORT_TARGET_HUMIDITY

        return features

    @property
    def name(self):
        """Return the name of the thermostat."""
        return getattr(self._client, VENSTAR_NAME)

    @property
    def unique_id(self):
        """Return the unique identifier of the thermostat."""
        return f"{self._config_entry.unique_id or self._config_entry.entry_id}-Thermostat-Device"

    @property
    def device_info(self):
        """Return the device info of the thermostat."""
        device_info = {
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": "Venstar",
            "name": self._config_entry.title,
            "model": getattr(self._client, VENSTAR_MODEL),
        }
        if self._config_entry.data.get(CONF_MAC) is not None:
            device_info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, self._config_entry.data.get(CONF_MAC))
            }

        return device_info

    @property
    def available(self):
        """Return availability of the thermostat."""
        return self.hass.data[DOMAIN][self._config_entry.entry_id][
            ENTRY_CONNECTION_STATE
        ]

    @property
    def precision(self):
        """Return the precision of the system.

        Venstar temperature values are passed back and forth in the
        API in C or F, with half-degree accuracy.
        """
        return PRECISION_HALVES

    @property
    def temperature_unit(self):
        """Return the unit of measurement, as defined by the API."""
        if getattr(self._client, VENSTAR_TEMPUNITS) == VENSTAR_TEMPUNITS_F:
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return VALID_FAN_STATES

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return VALID_THERMOSTAT_MODES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.get_indoor_temp()

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._client.get_indoor_humidity()

    @property
    def hvac_mode(self):
        """Return current operation mode ie. heat, cool, auto."""
        if getattr(self._client, VENSTAR_MODE) == VENSTAR_MODE_HEAT:
            return HVAC_MODE_HEAT
        if getattr(self._client, VENSTAR_MODE) == VENSTAR_MODE_COOL:
            return HVAC_MODE_COOL
        if getattr(self._client, VENSTAR_MODE) == VENSTAR_MODE_AUTO:
            return HVAC_MODE_AUTO
        return HVAC_MODE_OFF

    @property
    def hvac_action(self):
        """Return current operation mode ie. heat, cool, auto."""
        if getattr(self._client, VENSTAR_STATE) == VENSTAR_STATE_IDLE:
            return CURRENT_HVAC_IDLE
        if getattr(self._client, VENSTAR_STATE) == VENSTAR_STATE_HEATING:
            return CURRENT_HVAC_HEAT
        if getattr(self._client, VENSTAR_STATE) == VENSTAR_STATE_COOLING:
            return CURRENT_HVAC_COOL
        return CURRENT_HVAC_OFF

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        if getattr(self._client, VENSTAR_FAN) == VENSTAR_FAN_ON:
            return FAN_ON
        return FAN_AUTO

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        return {
            ATTR_FAN_STATE: getattr(self._client, VENSTAR_FANSTATE),
            ATTR_HVAC_STATE: getattr(self._client, VENSTAR_STATE),
        }

    @property
    def target_temperature(self):
        """Return the target temperature we try to reach."""
        if getattr(self._client, VENSTAR_MODE) == VENSTAR_MODE_HEAT:
            return getattr(self._client, VENSTAR_HEATTEMP)
        if getattr(self._client, VENSTAR_MODE) == VENSTAR_MODE_COOL:
            return getattr(self._client, VENSTAR_COOLTEMP)
        return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temp if auto mode is on."""
        if getattr(self._client, VENSTAR_MODE) == VENSTAR_MODE_AUTO:
            return getattr(self._client, VENSTAR_HEATTEMP)
        return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temp if auto mode is on."""
        if getattr(self._client, VENSTAR_MODE) == VENSTAR_MODE_AUTO:
            return getattr(self._client, VENSTAR_COOLTEMP)
        return None

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return getattr(self._client, VENSTAR_HUM_SETPOINT)

    @property
    def min_humidity(self):
        """Return the minimum humidity. Hardcoded to 0 in API."""
        return 0

    @property
    def max_humidity(self):
        """Return the maximum humidity. Hardcoded to 60 in API."""
        return 60

    @property
    def preset_mode(self):
        """Return current preset."""
        if getattr(self._client, VENSTAR_AWAY) == VENSTAR_AWAY_AWAY:
            return PRESET_AWAY
        if getattr(self._client, VENSTAR_SCHEDULE) == VENSTAR_SCHEDULE_DISABLED:
            return HOLD_MODE_TEMPERATURE
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return valid preset modes."""
        return VALID_PRESET_MODES

    def _set_operation_mode(self, operation_mode):
        """Change the operation mode (internal)."""
        if operation_mode == HVAC_MODE_HEAT:
            success = self._client.set_mode(VENSTAR_MODE_HEAT)
        elif operation_mode == HVAC_MODE_COOL:
            success = self._client.set_mode(VENSTAR_MODE_COOL)
        elif operation_mode == HVAC_MODE_AUTO:
            success = self._client.set_mode(VENSTAR_MODE_AUTO)
        else:
            success = self._client.set_mode(VENSTAR_MODE_OFF)

        if not success:
            _LOGGER.error("Failed to change the operation mode")
        return success

    def set_temperature(self, **kwargs):
        """Set a new target temperature."""
        set_temp = True
        operation_mode = kwargs.get(ATTR_HVAC_MODE)
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if operation_mode and MODE_MAP.get(operation_mode) != getattr(
            self._client, VENSTAR_MODE
        ):
            set_temp = self._set_operation_mode(operation_mode)

        if set_temp:
            if (
                MODE_MAP.get(operation_mode, getattr(self._client, VENSTAR_MODE))
                == VENSTAR_MODE_HEAT
            ):
                success = self._client.set_setpoints(
                    temperature, getattr(self._client, VENSTAR_COOLTEMP)
                )
            elif (
                MODE_MAP.get(operation_mode, getattr(self._client, VENSTAR_MODE))
                == VENSTAR_MODE_COOL
            ):
                success = self._client.set_setpoints(
                    getattr(self._client, VENSTAR_HEATTEMP), temperature
                )
            elif (
                MODE_MAP.get(operation_mode, getattr(self._client, VENSTAR_MODE))
                == VENSTAR_MODE_AUTO
            ):
                success = self._client.set_setpoints(temp_low, temp_high)
            else:
                success = False
                _LOGGER.error(
                    "The thermostat is currently not in a mode "
                    "that supports target temperature: %s",
                    operation_mode,
                )

            if not success:
                _LOGGER.error("Failed to change the temperature")

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode == STATE_ON:
            success = self._client.set_fan(VENSTAR_FAN_ON)
        else:
            success = self._client.set_fan(VENSTAR_FAN_AUTO)

        if not success:
            _LOGGER.error("Failed to change the fan mode")

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        self._set_operation_mode(hvac_mode)

    def set_humidity(self, humidity):
        """Set new target humidity."""
        success = self._client.set_hum_setpoint(humidity)

        if not success:
            _LOGGER.error("Failed to change the target humidity level")

    def set_preset_mode(self, preset_mode):
        """Set the hold mode."""
        if preset_mode == PRESET_AWAY:
            success = self._client.set_away(VENSTAR_AWAY_AWAY)
        elif preset_mode == HOLD_MODE_TEMPERATURE:
            success = self._client.set_away(VENSTAR_AWAY_HOME)
            success = success and self._client.set_schedule(VENSTAR_SCHEDULE_DISABLED)
        elif preset_mode == PRESET_NONE:
            success = self._client.set_away(VENSTAR_AWAY_HOME)
            success = success and self._client.set_schedule(VENSTAR_SCHEDULE_ENABLED)
        else:
            _LOGGER.error("Unknown hold mode: %s", preset_mode)
            success = False

        if not success:
            _LOGGER.error("Failed to change the schedule/hold state")
