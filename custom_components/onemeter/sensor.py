import json
import time
import logging
from datetime import datetime, timedelta
from collections import deque
from calendar import monthrange

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components import mqtt
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.typing import StateType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "onemeter"

# Stałe konfiguracji
CONF_DEVICE_ID = "device_id"
CONF_MAC = "mac"
CONF_TOPIC = "topic"
CONF_IMPULSES_PER_KWH = "impulses_per_kwh"
CONF_MAX_POWER_KW = "max_power_kw"
CONF_TIMEOUT = "power_timeout_seconds"
CONF_POWER_AVERAGE_WINDOW = "power_average_window"
CONF_INITIAL_KWH = "initial_kwh"
CONF_MONTHLY_USAGE_KWH = "monthly_usage_kwh"


class OneMeterCoordinator(DataUpdateCoordinator):
    """Koordynator zarządzający połączeniem MQTT i danymi."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        config = {**entry.data, **entry.options}

        self.device_id = config.get(CONF_DEVICE_ID, "om9613")
        self.target_mac = config.get(CONF_MAC, "E58D81019613")
        self.base_topic = config.get(CONF_TOPIC, "onemeter/s10/v1")

        # Parametry
        self.impulses_per_kwh = config.get(CONF_IMPULSES_PER_KWH, 1000)
        self.max_power_kw = int(config.get(CONF_MAX_POWER_KW, 20))  # 🔧 int
        self.power_timeout_seconds = config.get(CONF_TIMEOUT, 300)
        self.power_history = deque(maxlen=config.get(CONF_POWER_AVERAGE_WINDOW, 2))
        self.initial_kwh_setting = config.get(CONF_INITIAL_KWH, 0.0)
        self.monthly_usage_kwh = config.get(CONF_MONTHLY_USAGE_KWH, 0.0)

        # Stany
        self.total_impulses = int(self.initial_kwh_setting * self.impulses_per_kwh)
        self.kwh_at_month_start = int(self.monthly_usage_kwh * self.impulses_per_kwh)
        self.last_month_checked = datetime.now().month
        self.month_start_timestamp = time.time()
        self.last_valid_power = 0.0
        self.last_impulse_times = deque(maxlen=2)
        self.unsubscribe_mqtt = None
        self.data = None

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=1))

    async def _async_update_data(self):
        """Aktualizuje dane co 60 minut."""
        if self.data is None:
            kwh = self.total_impulses / self.impulses_per_kwh
            self.data = {
                "power_kw": 0.0,
                "kwh": kwh,
                "last_impulse_time": time.time() - self.power_timeout_seconds - 1,
            }
        self.async_set_updated_data(self.data)
        return self.data

    @callback
    async def _async_message_received(self, msg):
        """Obsługuje wiadomości MQTT."""
        try:
            payload = json.loads(msg.payload.decode() if isinstance(msg.payload, bytes) else msg.payload)
            dev_list = payload.get("dev_list", [])
            onemeter_entry = next((d for d in dev_list if d.get("mac", "").upper() == self.target_mac.upper()), None)
            if not onemeter_entry:
                return

            ts_ms = onemeter_entry.get("ts")
            if not isinstance(ts_ms, int):
                return

            now = ts_ms / 1000
            self.total_impulses += 1
            self.last_impulse_times.append(now)
            power_kw = 0.0
            if len(self.last_impulse_times) == 2:
                dt = self.last_impulse_times[1] - self.last_impulse_times[0]
                if dt > 0:
                    power_kw = min(3600 / (self.impulses_per_kwh * dt), self.max_power_kw)
                    self.last_valid_power = power_kw
            self.power_history.append(self.last_valid_power)
            kwh = self.total_impulses / self.impulses_per_kwh
            self.data = {
                "power_kw": sum(self.power_history) / len(self.power_history),
                "kwh": kwh,
                "last_impulse_time": now,
            }
            self.async_set_updated_data(self.data)
        except Exception as e:
            _LOGGER.error(f"Błąd MQTT: {e}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = OneMeterCoordinator(hass, entry)
    await coordinator._async_update_data()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    async_add_entities([
        OneMeterEnergySensor(coordinator),
        OneMeterPowerSensor(coordinator),
        OneMeterForecastSensor(coordinator),
    ])
    return True


class OneMeterBaseSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: OneMeterCoordinator):
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="OneMeter",
            manufacturer="OneMeter",
            model="Energy Meter",
            sw_version="2.1.1",
        )


class OneMeterEnergySensor(OneMeterBaseSensor):
    _attr_translation_key = "energy_kwh"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        return round(self.coordinator.data.get("kwh", 0.0), 3) if self.coordinator.data else None


class OneMeterPowerSensor(OneMeterBaseSensor):
    _attr_translation_key = "power_kw"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        if time.time() - self.coordinator.data.get("last_impulse_time", 0) > self.coordinator.power_timeout_seconds:
            return 0.0
        return round(self.coordinator.data.get("power_kw", 0.0), 3)


class OneMeterForecastSensor(OneMeterBaseSensor):
    _attr_translation_key = "monthly_forecast_kwh"
    _attr_name = "Prognoza miesięczna"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        now = datetime.now()
        elapsed_days = (time.time() - self.coordinator.month_start_timestamp) / 86400
        used = (self.coordinator.total_impulses - self.coordinator.kwh_at_month_start) / self.coordinator.impulses_per_kwh
        if elapsed_days <= 0 or used <= 0:
            return 0
        days_in_month = monthrange(now.year, now.month)[1]
        forecast = (used / elapsed_days) * days_in_month
        return round(forecast, 1)
