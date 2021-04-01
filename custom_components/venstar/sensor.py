"""Support for Venstar WiFi thermostat sensors."""
import logging

from homeassistant.const import CONF_SENSORS, TIME_MINUTES
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_RUNTIMES,
    DEFAULT_CONF_RUNTIMES,
    DEFAULT_CONF_SENSORS,
    DOMAIN,
    ENTRY_API,
    ENTRY_CONNECTION_STATE,
    ENTRY_COORDINATOR,
    RUNTIME_ATTRIBUTES,
    RUNTIME_TS,
    SENSOR_ATTRIBUTES,
    SENSOR_ID,
    SENSOR_PARAM_CLASS,
    SENSOR_PARAM_NAME,
    SENSOR_PARAM_UNIT,
    SENSOR_TEMPERATURE,
    VENSTAR_MODEL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Venstar sensors."""
    api = hass.data[DOMAIN][entry.entry_id][ENTRY_API]
    devices = []

    if entry.options.get(CONF_SENSORS, DEFAULT_CONF_SENSORS):
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

    if entry.options.get(CONF_RUNTIMES, DEFAULT_CONF_RUNTIMES):
        for sensor in api.runtimes[-1].keys():
            if sensor == RUNTIME_TS:
                continue

            devices.append(
                VenstarRuntimeSensor(
                    hass.data[DOMAIN][entry.entry_id][ENTRY_COORDINATOR],
                    api,
                    entry,
                    sensor,
                )
            )

    if devices:
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
        return f"{self._sensor} {SENSOR_ATTRIBUTES[self._attr][SENSOR_PARAM_NAME]}"

    @property
    def unique_id(self):
        """Return the unique identifier of this sensor."""
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
        if (
            self._attr in SENSOR_ATTRIBUTES
            and SENSOR_PARAM_CLASS in SENSOR_ATTRIBUTES[self._attr]
        ):
            return SENSOR_ATTRIBUTES[self._attr][SENSOR_PARAM_CLASS]

        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        state = self._api.get_sensor(self._sensor, self._attr)
        if type(state) is int or type(state) is float:
            return state

        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        if (
            self._attr in SENSOR_ATTRIBUTES
            and SENSOR_PARAM_UNIT in SENSOR_ATTRIBUTES[self._attr]
        ):
            if (
                self._attr == SENSOR_TEMPERATURE
                and self._api.tempunits
                in SENSOR_ATTRIBUTES[self._attr][SENSOR_PARAM_UNIT]
            ):
                return SENSOR_ATTRIBUTES[self._attr][SENSOR_PARAM_UNIT][
                    self._api.tempunits
                ]

            return SENSOR_ATTRIBUTES[self._attr][SENSOR_PARAM_UNIT]

        return None


class VenstarRuntimeSensor(CoordinatorEntity, Entity):
    """Representation of an Venstar alert sensor."""

    def __init__(self, coordinator, api, config_entry, sensor):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._config_entry = config_entry
        self._sensor = sensor

    @property
    def name(self):
        """Return the name of the this sensor."""
        return f"{self._config_entry.title} {RUNTIME_ATTRIBUTES.get(self._sensor,{}).get(SENSOR_PARAM_NAME,self._sensor)} Runtime"

    @property
    def unique_id(self):
        """Return the unique identifier of this sensor."""
        return f"{self._config_entry.unique_id or self._config_entry.entry_id}-runtime-{self._sensor.replace(' ', '_')}"

    @property
    def device_info(self):
        """Return device information for this sensor."""
        unique_id_thermostat = f"{self._config_entry.unique_id or self._config_entry.entry_id}-Thermostat-Device"

        return {
            "identifiers": {(DOMAIN, unique_id_thermostat)},
            "manufacturer": "Venstar",
            "name": self._config_entry.title,
            "model": getattr(self._api, VENSTAR_MODEL),
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
    def state(self):
        """Return the state of the sensor."""
        if self._sensor in self._api.runtimes[-1]:
            state = self._api.runtimes[-1][self._sensor]
        if type(state) is int or type(state) is float:
            return state

        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return TIME_MINUTES
