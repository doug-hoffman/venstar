"""Constants for the venstar integration."""

from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)

from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

ATTR_FAN_STATE = "fan_state"
ATTR_HVAC_STATE = "hvac_mode"

DOMAIN = "venstar"

CONF_HUMIDIFIER = "humidifier"

DEFAULT_CONF_HUMIDIFIER = False
DEFAULT_CONF_PASSWORD = ""
DEFAULT_CONF_PIN = ""
DEFAULT_CONF_PORT = ""
DEFAULT_CONF_SCAN_INTERVAL = 10
DEFAULT_CONF_SENSORS = True
DEFAULT_CONF_SSL = False
DEFAULT_CONF_TIMEOUT = 5
DEFAULT_CONF_USERNAME = ""

ENTRY_API = "api"
ENTRY_CONNECTION_STATE = "connection_state"
ENTRY_COORDINATOR = "coordinator"
ENTRY_UNDO_UPDATE_LISTENER = "undo_update_listener"

HOLD_MODE_OFF = "off"
HOLD_MODE_TEMPERATURE = "temperature"

SENSOR_BATTERY = "battery"
SENSOR_HUMIDITY = "hum"
SENSOR_ID = "id"
SENSOR_TEMPERATURE = "temp"

TEMPUNITS_F = 0
TEMPUNITS_C = 1

SENSOR_ATTRIBUTES = {
    SENSOR_BATTERY: {
        "name": "Battery Level",
        "class": DEVICE_CLASS_BATTERY,
        "unit": PERCENTAGE,
    },
    SENSOR_HUMIDITY: {
        "name": "Humidity",
        "class": DEVICE_CLASS_HUMIDITY,
        "unit": PERCENTAGE,
    },
    SENSOR_ID: {"name": "ID"},
    SENSOR_TEMPERATURE: {
        "name": "Temperature",
        "class": DEVICE_CLASS_TEMPERATURE,
        "unit": {
            TEMPUNITS_F: TEMP_FAHRENHEIT,
            TEMPUNITS_C: TEMP_CELSIUS,
        },
    },
}

VALID_FAN_STATES = [STATE_ON, HVAC_MODE_AUTO]
VALID_THERMOSTAT_MODES = [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF, HVAC_MODE_AUTO]
