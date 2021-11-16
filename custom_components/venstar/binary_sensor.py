"""Support for Venstar WiFi thermostat binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.const import CONF_SENSORS
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALERT_ACTIVE,
    ALERT_NAME,
    CONF_ALERTS,
    DEFAULT_CONF_ALERTS,
    DOMAIN,
    ENTRY_API,
    ENTRY_CONNECTION_STATE,
    ENTRY_COORDINATOR,
    VENSTAR_MODEL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Venstar sensors."""
    api = hass.data[DOMAIN][entry.entry_id][ENTRY_API]
    devices = []

    if entry.options.get(CONF_ALERTS, DEFAULT_CONF_ALERTS):
        for sensor in api.alerts:
            devices.append(
                VenstarAlertSensor(
                    hass.data[DOMAIN][entry.entry_id][ENTRY_COORDINATOR],
                    api,
                    entry,
                    sensor.get(ALERT_NAME),
                )
            )

    if devices:
        async_add_entities(devices, True)


class VenstarAlertSensor(CoordinatorEntity, BinarySensorEntity):
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
        return f"{self._config_entry.title} {self._sensor}"

    @property
    def unique_id(self):
        """Return the unique identifier of this sensor."""
        return f"{self._config_entry.unique_id or self._config_entry.entry_id}-alert-{self._sensor.replace(' ', '_')}"

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
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_PROBLEM

    @property
    def is_on(self):
        """Return the state of the sensor."""
        if isinstance(self._api.alerts, list):
            for sensor in self._api.alerts:
                if sensor.get(ALERT_NAME) == self._sensor and isinstance(sensor.get(ALERT_ACTIVE), bool):
                    return sensor.get(ALERT_ACTIVE)
