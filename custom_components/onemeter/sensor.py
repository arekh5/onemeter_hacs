import json
import logging
from datetime import datetime
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_KILO_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import paho.mqtt.client as mqtt
import threading
import time
from collections import deque

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    """Setup OneMeter sensors from config entry."""
    sensor_manager = OneMeterMQTTManager(hass, entry, async_add_entities)
    await hass.async_add_executor_job(sensor_manager.start)
    _LOGGER.info("OneMeter integration started.")


class OneMeterMQTTManager:
    """Handles MQTT connection and updates Home Assistant sensors."""

    def __init__(self, hass, entry, async_add_entities):
        self.hass = hass
        self.mqtt_config = entry.data
        self.async_add_entities = async_add_entities

        # Create sensors
        self.energy_sensor = OneMeterEnergySensor(self.mqtt_config["device_name"], "energy")
        self.power_sensor = OneMeterPowerSensor(self.mqtt_config["device_name"], "power")

        # Track impulses
        self.total_impulses = 0
        self.impulse_window = deque()
        self.last_timestamp = None

        self.client = mqtt.Client()
        self.client.username_pw_set(self.mqtt_config["mqtt_user"], self.mqtt_config["mqtt_pass"])
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def start(self):
        """Run MQTT client in separate thread."""
        self.async_add_entities([self.energy_sensor, self.power_sensor])
        self.client.connect(
            self.mqtt_config["mqtt_broker"],
            self.mqtt_config["mqtt_port"],
            60
        )
        threading.Thread(target=self.client.loop_forever, daemon=True).start()

    def on_connect(self, client, userdata, flags, rc):
        _LOGGER.info("Connected to MQTT broker")
        client.subscribe("onemeter/s10/v1")
        client.publish("onemeter/energy/om9613/status", "online", qos=1, retain=True)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            dev_list = payload.get("dev_list", [])
            if not dev_list:
                return

            device = dev_list[0]
            ts = device.get("ts")

            if ts == self.last_timestamp:
                return
            self.last_timestamp = ts

            # impulse count
            delta = 1
            self.total_impulses += delta

            now = time.time()
            self.impulse_window.append(now)
            while self.impulse_window and (now - self.impulse_window[0]) > self.mqtt_config.get("window_seconds", 60):
                self.impulse_window.popleft()

            # power calculation
            power_kw = (len(self.impulse_window) / 1000) * (3600 / self.mqtt_config.get("window_seconds", 60))
            max_power = self.mqtt_config.get("max_power_kw", 20.0)
            if max_power and power_kw > max_power:
                power_kw = max_power

            # energy in kWh
            kwh = self.total_impulses / 1000

            # update sensors in Home Assistant
            self.hass.add_job(self.energy_sensor.async_set_native_value, round(kwh, 3))
            self.hass.add_job(self.power_sensor.async_set_native_value, round(power_kw, 2))

            _LOGGER.debug(f"Updated sensors: {kwh:.3f} kWh, {power_kw:.2f} kW")

        except Exception as e:
            _LOGGER.error(f"Error processing MQTT message: {e}")


class OneMeterBaseSensor(SensorEntity):
    """Base class with device info and unique ID."""

    def __init__(self, device_name, sensor_type):
        self.device_name = device_name
        self.sensor_type = sensor_type
        self._attr_name = f"{device_name} {sensor_type.capitalize()}"
        self._attr_unique_id = f"{device_name.lower().replace(' ', '_')}_{sensor_type}"
        self._attr_icon = "mdi:flash"

    @property
    def device_info(self):
        """Return device info for grouping sensors in Home Assistant."""
        return {
            "identifiers": {(self.device_name.lower().replace(' ', '_'),)},
            "name": self.device_name,
            "manufacturer": "OneMeter",
            "model": "S10"
        }


class OneMeterEnergySensor(OneMeterBaseSensor):
    """Total energy sensor."""

    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

    async def async_set_native_value(self, value):
        self._attr_native_value = value
        self.async_write_ha_state()


class OneMeterPowerSensor(OneMeterBaseSensor):
    """Instant power sensor."""

    _attr_native_unit_of_measurement = POWER_KILO_WATT

    async def async_set_native_value(self, value):
        self._attr_native_value = value
        self.async_write_ha_state()
