"""Support for Venstar WiFi thermostat sensors."""
import logging

from venstarcolortouch import VenstarColorTouch
import voluptuous as vol

from homeassistant.const import (
    CONF_SENSORS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import (
    DEFAULT_CONF_SENSORS,
    DOMAIN,
    ENTRY_API,
    ENTRY_CONNECTION_STATE,
    ENTRY_COORDINATOR,
    SENSOR_ATTRIBUTES,
    SENSOR_BATTERY,
    SENSOR_HUMIDITY,
    SENSOR_ID,
    SENSOR_TEMPERATURE,
    TEMPUNITS_C,
    TEMPUNITS_F,
    UNIT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Venstar sensors."""
    if not entry.options.get(CONF_SENSORS, DEFAULT_CONF_SENSORS):
        return

    api = hass.data[DOMAIN][entry.entry_id][ENTRY_API]
    devices = []
    for sensor in api.get_sensor_list():
        for attr in SENSOR_ATTRIBUTES:
            if attr == SENSOR_ID:
                continue

            if api.get_sensor(sensor, attr):
                devices.append(
                    VenstarSensor(
                        hass.data[DOMAIN][entry.entry_id][ENTRY_COORDINATOR],
                        api,
                        entry,
                        sensor,
                        attr,
                    )
                )

    async_add_entities(devices, True)


class VenstarSensor(CoordinatorEntity, Entity):
    """Representation of an Venstar sensor."""

    def __init__(self, coordinator, api, config_entry, sensor, attr):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._config_entry = config_entry
        self._sensor = sensor
        self._attr = attr

    @property
    def name(self):
        """Return the name of the this sensor."""
        return self._sensor + " " + SENSOR_ATTRIBUTES[self._attr]["name"]

    @property
    def unique_id(self):
        """Return the unique identifer of this sensor."""
        return f"{self._config_entry.unique_id or self._config_entry.entry_id}-{self._sensor.replace(' ', '_')}-{self._attr.replace(' ', '_')}"

    @property
    def device_info(self):
        """Return device information for this sensor."""
        unique_id_device = f"{self._config_entry.unique_id or self._config_entry.entry_id}-{self._sensor.replace(' ', '_')}"
        unique_id_thermostat = f"{self._config_entry.unique_id or self._config_entry.entry_id}-Thermostat-Device"

        return {
            "identifiers": {(DOMAIN, unique_id_device)},
            "name": self._sensor,
            "manufacturer": "Venstar",
            "model": f"{self._api.get_sensor(self._sensor, 'type') or 'Unknown'} Sensor",
            "via_device": (DOMAIN, unique_id_thermostat),
        }

    @property
    def available(self):
        """Return availability of the sensor."""
        return (
            self.state is not None
            and self.hass.data[DOMAIN][self._config_entry.entry_id][
                ENTRY_CONNECTION_STATE
            ]
        )

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self._attr in SENSOR_ATTRIBUTES:
            return SENSOR_ATTRIBUTES[self._attr]["class"]

        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        state = self._api.get_sensor(self._sensor, self._attr)
        if type(state) is int or type(state) is float:
            return state
        else:
            return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        if self._attr == SENSOR_TEMPERATURE:
            return UNIT[self._attr][self._api.tempunits]

        return UNIT[self._attr]
