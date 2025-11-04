import json
import time
import logging
from datetime import datetime
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
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components import mqtt
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.typing import StateType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "onemeter"

# ----------------------------------------------------------------------
# KLASA KOORDYNATORA DANYCH (ZARZĄDZA KLIENTEM MQTT)
# ----------------------------------------------------------------------

class OneMeterCoordinator(DataUpdateCoordinator):
    """Koordynator zarządzający połączeniem MQTT i danymi."""
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self.mqtt_config = entry.data
        self.device_id = "om9613"
        self.base_topic = "onemeter/s10/v1"
        
        # --- Stan MQTT ---
        self.unsubscribe_mqtt = None

        # --- Stan Licznika ---
        self.total_impulses = 0
        self.last_impulse_times = deque(maxlen=2)
        self.last_valid_power = 0.0
        
        # --- Parametry ---
        self.impulses_per_kwh = self.mqtt_config.get("impulses_per_kwh", 1000)
        self.max_power_kw = self.mqtt_config.get("max_power_kw", 20.0)
        self.power_update_interval = self.mqtt_config.get("power_update_interval", 5) 
        self.power_timeout_seconds = self.mqtt_config.get("power_timeout_seconds", 300)
        self.power_history = deque(maxlen=self.mqtt_config.get("power_average_window", 2))
        
        # --- Zapisywany Stan Prognozy ---
        self.kwh_at_month_start = 0.0
        self.last_month_checked = datetime.now().month
        self.month_start_timestamp = time.time()
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None # Koordynator Event-Driven
        )

    @callback
    async def _async_message_received(self, msg):
        """Asynchroniczna obsługa wiadomości MQTT."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            dev_list = payload.get("dev_list", [])
            if not dev_list:
                return

            now = time.time()
            self.total_impulses += 1 
            self.last_impulse_times.append(now) 

            # --- 1. Obliczenie Mocy (Delta t) ---
            power_kw = 0.0
            if len(self.last_impulse_times) == 2:
                time_diff_t = self.last_impulse_times[1] - self.last_impulse_times[0]
                if time_diff_t > 0:
                    power_kw = 3600 / (self.impulses_per_kwh * time_diff_t)
                    if power_kw > self.max_power_kw:
                         power_kw = self.max_power_kw
                    self.last_valid_power = power_kw
            
            self.power_history.append(self.last_valid_power)
            
            # --- 2. Obliczenie Energii ---
            kwh = self.total_impulses / self.impulses_per_kwh
            
            # --- 3. Aktualizacja danych i powiadomienie encji ---
            self.data = {
                "power_kw": sum(self.power_history) / len(self.power_history),
                "kwh": kwh,
                "last_impulse_time": now,
                "last_impulse_kw": self.last_valid_power,
            }
            self.async_set_updated_data(self.data)
            
        except Exception as e:
            _LOGGER.error(f"❌ Błąd przetwarzania wiadomości MQTT: {e}")

    async def async_added_to_hass(self) -> None:
        """Subskrypcja MQTT po starcie integracji."""
        self.unsubscribe_mqtt = await mqtt.async_subscribe(
            self.hass,
            self.base_topic,
            self._async_message_received,
            qos=1,
            encoding="utf-8"
        )
        await super().async_added_to_hass()
        
    async def async_will_remove_from_hass(self) -> None:
        """Usunięcie subskrypcji MQTT."""
        if self.unsubscribe_mqtt:
            self.unsubscribe_mqtt()
        await super().async_will_remove_from_hass()


# ----------------------------------------------------------------------
# ASYNCHRONICZNE SETUP (TWORZENIE ENCJACH)
# ----------------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Tworzenie encji sensorów."""
    
    coordinator = OneMeterCoordinator(hass, entry)
    # POPRAWKA BŁĘDU NotImplementedError: usunięto linijkę wymuszającą odświeżanie.

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async_add_entities([
        OneMeterEnergySensor(coordinator),
        OneMeterPowerSensor(coordinator),
        OneMeterForecastSensor(coordinator),
    ])


# ----------------------------------------------------------------------
# KLASY ENCJACH (SENSORÓW)
# ----------------------------------------------------------------------

class OneMeterBaseSensor(RestoreEntity):
    """Bazowa klasa sensora."""
    
    def __init__(self, coordinator: OneMeterCoordinator):
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="OneMeter",
            manufacturer="OneMeter",
            model="OM9613 Energy Monitor",
        )
        self._attr_should_poll = False
        
    async def async_added_to_hass(self) -> None:
        """Ładowanie stanu po dodaniu do HA."""
        await super().async_added_to_hass()
        self.coordinator.async_add_listener(self.async_write_ha_state)
        
    async def async_will_remove_from_hass(self) -> None:
        """Usunięcie nasłuchiwania."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)
        
    @property
    def available(self) -> bool:
        """Sprawdza, czy koordynator jest dostępny (ma dane)."""
        return self.coordinator.data is not None


class OneMeterEnergySensor(OneMeterBaseSensor):
    """Sensor całkowitej energii (kWh)."""
    
    _attr_has_entity_name = True
    _attr_name = "Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR 
    
    def __init__(self, coordinator: OneMeterCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_energy_kwh"
        
    @property
    def native_value(self) -> StateType:
        """Zwraca całkowite zużycie kWh."""
        return round(self.coordinator.data.get("kwh", 0.0), 3)


class OneMeterPowerSensor(OneMeterBaseSensor):
    """Sensor mocy chwilowej (kW)."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    # POPRAWKA BŁĘDU KILO_WATTS: Użyto prawidłowej stałej KILO_WATT
    _attr_unit_of_measurement = UnitOfPower.KILO_WATT 
    
    def __init__(self, coordinator: OneMeterCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_power_kw"

    @property
    def native_value(self) -> StateType:
        """Zwraca uśrednioną moc chwilową kW."""
        now = time.time()
        
        last_impulse_time = self.coordinator.data.get("last_impulse_time", 0)
        power = self.coordinator.data.get("power_kw", 0.0)

        if (now - last_impulse_time) > self.coordinator.power_timeout_seconds:
            return 0.0
        
        return round(power, 3)

    
class OneMeterForecastSensor(OneMeterBaseSensor):
    """Sensor prognozy miesięcznej (kWh) z persystencją stanu."""

    _attr_has_entity_name = True
    _attr_name = "Monthly Forecast"
    # POPRAWKA WALIDACJI HA: Usunięto SensorDeviceClass.ENERGY, 
    # ponieważ konfliktował z SensorStateClass.MEASUREMENT.
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: OneMeterCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_forecast_kwh"
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Ładowanie stanu prognozy po starcie HA (PERSYSTENCJA)."""
        await super().async_added_to_hass()
        
        last_state = await self.async_get_last_state()
        
        if last_state and last_state.attributes:
            kwh_start = last_state.attributes.get('kwh_at_month_start')
            last_month = last_state.attributes.get('last_month_checked')

            if kwh_start is not None and last_month is not None:
                try:
                    self.coordinator.kwh_at_month_start = float(kwh_start)
                    self.coordinator.last_month_checked = int(last_month)
                    _LOGGER.info(f"✅ Prognoza: Odzyskano stan: {kwh_start} kWh z miesiąca {last_month}.")
                except ValueError:
                    _LOGGER.warning("Nieprawidłowe wartości w zapisanym stanie prognozy.")
        
        self.coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def native_value(self) -> StateType:
        """Obliczenie i zapisanie prognozy miesięcznej."""
        
        kwh = self.coordinator.data.get("kwh", 0.0)
        forecast_kwh = 0.0
        now_dt = datetime.now()
        current_month = now_dt.month
        
        # 1. Sprawdzenie zmiany miesiąca
        if current_month != self.coordinator.last_month_checked:
            _LOGGER.info(f"🔄 Zmiana miesiąca wykryta. Reset prognozy.")
            self.coordinator.kwh_at_month_start = kwh 
            self.coordinator.last_month_checked = current_month
            self.coordinator.month_start_timestamp = time.time() 
        elif self.coordinator.kwh_at_month_start == 0.0 and kwh > 0:
             self.coordinator.kwh_at_month_start = kwh
             self.coordinator.month_start_timestamp = time.time()

        # 2. Obliczenia prognozy
        current_month_kwh = kwh - self.coordinator.kwh_at_month_start
        elapsed_days = (time.time() - self.coordinator.month_start_timestamp) / (24 * 3600)
        
        if elapsed_days > 0.01 and current_month_kwh > 0:
            days_in_month = monthrange(now_dt.year, current_month)[1]
            forecast_kwh = (current_month_kwh / elapsed_days) * days_in_month
        
        self._attr_extra_state_attributes = {
            "kwh_at_month_start": round(self.coordinator.kwh_at_month_start, 3),
            "last_month_checked": self.coordinator.last_month_checked,
            "current_month_kwh": round(current_month_kwh, 3)
        }

        return round(forecast_kwh, 3)