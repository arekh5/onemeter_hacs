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

# Stałe Konfiguracyjne (lokalna definicja dla spójności)
CONF_DEVICE_ID = "device_id"
CONF_MAC = "mac"
CONF_TOPIC = "topic"
CONF_IMPULSES_PER_KWH = "impulses_per_kwh"
CONF_MAX_POWER_KW = "max_power_kw"
CONF_TIMEOUT = "power_timeout_seconds"
CONF_POWER_AVERAGE_WINDOW = "power_average_window"
CONF_INITIAL_KWH = "initial_kwh" 

# ----------------------------------------------------------------------
# KLASA KOORDYNATORA DANYCH (ZARZĄDZA KLIENTEM MQTT)
# ----------------------------------------------------------------------

class OneMeterCoordinator(DataUpdateCoordinator):
    """Koordynator zarządzający połączeniem MQTT i danymi."""
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        
        config = {**entry.data, **entry.options}
        
        # Używamy parametrów z konfiguracji
        self.device_id = config.get(CONF_DEVICE_ID, "om9613")
        self.target_mac = config.get(CONF_MAC, "E58D81019613") 
        self.base_topic = config.get(CONF_TOPIC, "onemeter/s10/v1") 
        
        # --- Stan MQTT ---
        self.unsubscribe_mqtt = None

        # --- Stan Licznika (odzyskiwany na starcie) ---
        self.total_impulses = 0 
        self.last_impulse_times = deque(maxlen=2) 
        self.last_valid_power = 0.0
        
        # --- Parametry ---
        self.impulses_per_kwh = config.get(CONF_IMPULSES_PER_KWH, 1000)
        self.max_power_kw = config.get(CONF_MAX_POWER_KW, 20.0)
        self.power_timeout_seconds = config.get(CONF_TIMEOUT, 300)
        self.power_history = deque(maxlen=config.get(CONF_POWER_AVERAGE_WINDOW, 2))
        
        self.initial_kwh_setting = config.get(CONF_INITIAL_KWH, 0.0)

        # --- Zapisywany Stan Prognozy (Persystencja) ---
        self.kwh_at_month_start = 0.0
        self.last_month_checked = datetime.now().month
        self.month_start_timestamp = time.time()
        
        # Inicjalizacja danych na start
        self.data = None
        self.last_update_success = False
        
        # ✅ POPRAWKA: Zmieniono super().__coordinator__ na super().__init__
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None 
        )

    def async_remove_listener(self, update_callback: callback) -> None:
        """Usuwa słuchacza, przekazując wywołanie do klasy bazowej."""
        super().async_remove_listener(update_callback)

    async def _async_update_data(self):
        """Metoda wymagana przez DataUpdateCoordinator."""
        return self.data
    
    async def _async_restore_state(self, restored_kwh: float):
        """Ustawia stan początkowy Koordynatora na podstawie odzyskanego kWh z encji."""
        self.total_impulses = int(restored_kwh * self.impulses_per_kwh)
        _LOGGER.info(f"✅ Koordynator: Ustawiono stan początkowy/odzyskany: {restored_kwh} kWh.") 
        
        self.kwh_at_month_start = restored_kwh
        
        self.data = {
            "power_kw": 0.0,
            "kwh": restored_kwh,
            "last_impulse_time": time.time() - self.power_timeout_seconds - 1, 
            "last_impulse_kw": 0.0,
        }
        self.last_update_success = True

    @callback
    async def _async_message_received(self, msg):
        """Asynchroniczna obsługa wiadomości MQTT."""
        
        try:
            if isinstance(msg.payload, bytes):
                raw_payload_str = msg.payload.decode("utf-8")
            elif isinstance(msg.payload, str):
                raw_payload_str = msg.payload
            else:
                 _LOGGER.error(f"❌ Nieznany typ payloadu MQTT: {type(msg.payload)}. Oczekiwano bytes lub str.")
                 return

            payload = json.loads(raw_payload_str)
            dev_list = payload.get("dev_list", [])
            
            target_mac_upper = self.target_mac.upper() 
            onemeter_entry = next((
                dev for dev in dev_list if dev.get("mac", "").upper() == target_mac_upper
            ), None)
            
            if not onemeter_entry:
                _LOGGER.debug(f"Odebrano wiadomość MQTT, ale nie znaleziono urządzenia OneMeter ({self.target_mac}). Ignorowanie.")
                return

            ts_ms = onemeter_entry.get("ts")
            
            if not isinstance(ts_ms, int) or ts_ms == 0:
                 _LOGGER.warning("Znaleziono urządzenie, ale klucz 'ts' jest nieprawidłowy lub brak. Ignorowanie.")
                 return
                 
            now = ts_ms / 1000 
            
            self.total_impulses += 1 
            self.last_impulse_times.append(now) 

            # --- 2. Obliczenie Mocy (Delta t) ---
            power_kw = 0.0
            if len(self.last_impulse_times) == 2:
                time_diff_t = self.last_impulse_times[1] - self.last_impulse_times[0]
                if time_diff_t > 0:
                    power_kw = 3600 / (self.impulses_per_kwh * time_diff_t)
                    if power_kw > self.max_power_kw:
                         power_kw = self.max_power_kw
                    self.last_valid_power = power_kw
            
            self.power_history.append(self.last_valid_power)
            
            # --- 3. Obliczenie Energii ---
            kwh = self.total_impulses / self.impulses_per_kwh
            avg_power_kw = sum(self.power_history) / len(self.power_history)
            
            # 💡 POPRAWIONA LOGIKA RESETU/SYNCHRONIZACJI MIESIĘCZNEJ (Z v2.0.48)
            now_dt = datetime.fromtimestamp(now) 
            current_month = now_dt.month
            
            if current_month != self.last_month_checked:
                _LOGGER.info(f"🔄 Zmiana miesiąca wykryta. Reset prognozy na {kwh} kWh.")
                self.kwh_at_month_start = kwh
                self.last_month_checked = current_month
                self.month_start_timestamp = now 
            elif self.kwh_at_month_start == 0.0 and kwh > 0:
                 _LOGGER.info(f"🔄 Pierwszy impuls po restarcie/instalacji. Ustawienie prognozy na {kwh} kWh.")
                 self.kwh_at_month_start = kwh
                 self.month_start_timestamp = now
                 
            # 💡 OBLICZENIE PROGNOZY
            forecast_kwh = 0.0
            current_month_kwh = kwh - self.kwh_at_month_start
            
            # Używamy timestampu impulsu jako aktualnego czasu
            elapsed_seconds = now - self.month_start_timestamp
            
            if elapsed_seconds > 60 and current_month_kwh > 0 and now_dt.month == self.last_month_checked:
                elapsed_days = elapsed_seconds / (24 * 3600)
                days_in_month = monthrange(now_dt.year, now_dt.month)[1]
                
                if elapsed_days > 0:
                    forecast_kwh = (current_month_kwh / elapsed_days) * days_in_month

            # --- 4. Aktualizacja danych Koordynatora ---
            self.data = {
                "power_kw": avg_power_kw,
                "kwh": kwh,
                "last_impulse_time": now,
                "last_impulse_kw": self.last_valid_power,
            }
            self.last_update_success = True
            self.async_set_updated_data(self.data)

            # --- 5. Ponowna publikacja przetworzonych danych do MQTT ---
            timestamp_dt = datetime.fromtimestamp(now)
            timestamp_str = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            mqtt_payload = {
                "timestamp": timestamp_str,
                "impulses": self.total_impulses,
                "kwh": round(kwh, 3),
                "power_kw": round(avg_power_kw, 3),
                "forecast_kwh": round(forecast_kwh, 3) 
            }
            
            state_topic = f"onemeter/energy/{self.device_id}/state"
            try:
                await mqtt.async_publish(
                    self.hass, 
                    state_topic, 
                    json.dumps(mqtt_payload), 
                    qos=1,             
                    retain=True        
                )
            except Exception as publish_e:
                 _LOGGER.error(f"❌ BŁĄD PUBLIKACJI: Nie udało się opublikować przetworzonego stanu na MQTT: {publish_e}")
            
        except json.JSONDecodeError as e:
            _LOGGER.error(f"❌ Błąd parsowania JSON wiadomości MQTT: {e}")
        except Exception as e:
            _LOGGER.error(f"❌ Błąd krytyczny przetwarzania wiadomości MQTT: {e}")

    async def async_added_to_hass(self) -> None:
        """Subskrypcja MQTT i ustawienie statusu urządzenia (po gotowości klienta)."""
        
        _LOGGER.info("🚨 Inicjowanie subskrypcji MQTT dla Koordynatora.")
        
        try:
            self.unsubscribe_mqtt = await mqtt.async_subscribe(
                self.hass,
                self.base_topic,
                self._async_message_received,
                qos=1,
                encoding="utf-8"
            )
            
            if callable(self.unsubscribe_mqtt):
                _LOGGER.info(f"✅ Subskrypcja tematu {self.base_topic} jest AKTYWNA.")
            else:
                 _LOGGER.error(f"❌ Subskrypcja tematu {self.base_topic} NIEUDANA.")

            # Publikacja statusu (zawsze retain=True)
            status_topic = f"onemeter/energy/{self.device_id}/status"
            await mqtt.async_publish(
                self.hass, 
                status_topic, 
                "online", 
                qos=1, 
                retain=True
            )
            _LOGGER.debug(f"✅ Opublikowano status 'online' na temacie: {status_topic}")

        except Exception as e:
            _LOGGER.error(f"🚨 BŁĄD KRYTYCZNY SUBKSKRYPCJI: Wystąpił błąd w async_added_to_hass: {e}")

    async def async_will_remove_from_hass(self) -> None:
        """Usuwanie subskrypcji i statusu offline (LWT)."""
        status_topic = f"onemeter/energy/{self.device_id}/status"
        try:
            # Publikacja statusu offline (zawsze retain=True)
            await mqtt.async_publish(
                self.hass, 
                status_topic, 
                "offline", 
                qos=1, 
                retain=True
            )
            _LOGGER.debug(f"🚪 Opublikowano status 'offline' na temacie: {status_topic}")
        except Exception as e:
            _LOGGER.error(f"❌ Nie udało się opublikować statusu MQTT 'offline': {e}")
        
        if self.unsubscribe_mqtt:
            self.unsubscribe_mqtt()
            
        pass 

# ----------------------------------------------------------------------
# ASYNCHRONICZNE SETUP (TWORZENIE ENCJACH)
# ----------------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Tworzenie encji sensorów z obsługą odzyskiwania stanu Koordynatora."""
    
    coordinator = OneMeterCoordinator(hass, entry)

    # 1. Odzyskujemy stan kWh 
    entity_id_to_restore = f"sensor.{coordinator.device_id}_energy_kwh"
    last_state = hass.states.get(entity_id_to_restore)
    
    restored_kwh = float(coordinator.initial_kwh_setting)
    
    if last_state and last_state.state:
        try:
            restored_kwh = float(last_state.state)
            _LOGGER.info(f"✅ Odzyskano ostatni stan sensora {entity_id_to_restore}: {restored_kwh} kWh.")
        except ValueError:
            _LOGGER.warning(f"Nie udało się odzyskać stanu: Nieprawidłowa wartość '{last_state.state}'. Używam wartości z konfiguracji: {restored_kwh} kWh.")

    # 2. Inicjalizujemy Koordynatora odzyskanym stanem
    await coordinator._async_restore_state(restored_kwh)
    
    await coordinator.async_added_to_hass() 
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # 4. Dodajemy Encje
    async_add_entities([
        OneMeterEnergySensor(coordinator),
        OneMeterPowerSensor(coordinator),
        OneMeterForecastSensor(coordinator),
    ])
    
    return True

# ----------------------------------------------------------------------
# KLASY ENCJACH (SENSORÓW)
# ----------------------------------------------------------------------

class OneMeterBaseSensor(SensorEntity):
    """Baza dla sensorów OneMeter."""
    _attr_has_entity_name = True
    _attr_translation_key: str 

    def __init__(self, coordinator: OneMeterCoordinator):
        self.coordinator = coordinator
        
        self._attr_unique_id = f"{coordinator.device_id}_{self._attr_translation_key}"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="OneMeter",
            manufacturer="OneMeter",
            model="Energy Meter",
            sw_version="2.0.48", # Wersja końcowa
        )

    @property
    def available(self) -> bool:
        """Zwraca True, jeśli koordynator ma dane."""
        return callable(self.coordinator.unsubscribe_mqtt)

    async def async_added_to_hass(self) -> None:
        """Rejestracja callbacku po dodaniu encji."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
        await super().async_added_to_hass()

class OneMeterEnergySensor(OneMeterBaseSensor, RestoreEntity):
    """Sensor energii (kWh), który odzyskuje stan (persistence)."""
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_translation_key = "energy_kwh" 
    
    _attr_extra_state_attributes = {}

    @property
    def native_value(self) -> StateType:
        """Zwraca obecną wartość energii w kWh."""
        if self.coordinator.data is not None:
            return round(self.coordinator.data.get("kwh", 0.0), 3)
        return None

class OneMeterPowerSensor(OneMeterBaseSensor):
    """Sensor mocy chwilowej (kW)."""
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "power_kw"

    @property
    def native_value(self) -> StateType:
        """Zwraca obecną wartość mocy w kW."""
        if self.coordinator.data is not None:
            time_since_impulse = time.time() - self.coordinator.data.get("last_impulse_time", 0)
            
            if time_since_impulse > self.coordinator.power_timeout_seconds:
                 return 0.0
                 
            return round(self.coordinator.data.get("power_kw", 0.0), 3)
        return None

class OneMeterForecastSensor(OneMeterBaseSensor, RestoreEntity):
    """Sensor prognozy miesięcznego zużycia (kWh)."""
    _attr_translation_key = "monthly_forecast_kwh" 
    _attr_name = "Prognoza miesięczna"
    
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> StateType:
        """Oblicza i zwraca prognozę."""
        
        if self.coordinator.data is None:
            return None
            
        kwh = self.coordinator.data.get("kwh", 0.0)
        
        kwh_at_month_start = self.coordinator.kwh_at_month_start
        month_start_timestamp = self.coordinator.month_start_timestamp
        
        forecast_kwh = 0.0
        current_month_kwh = kwh - kwh_at_month_start
        
        # Używamy timestampu ostatniego impulsu jako referencji czasu
        now = self.coordinator.data.get("last_impulse_time", time.time())
        now_dt = datetime.fromtimestamp(now)
        
        # Obliczenie upływających sekund od początku okresu
        elapsed_seconds = now - month_start_timestamp
        
        # Wymagamy minimum 60 sekund i zużycia większego niż 0
        if elapsed_seconds > 60 and current_month_kwh > 0 and now_dt.month == self.coordinator.last_month_checked:
            elapsed_days = elapsed_seconds / (24 * 3600)
            days_in_month = monthrange(now_dt.year, now_dt.month)[1]
            
            # W obliczeniach prognozy używamy już tylko dni
            if elapsed_days > 0:
                forecast_kwh = (current_month_kwh / elapsed_days) * days_in_month
        
        self._attr_extra_state_attributes = {
            "kwh_at_month_start": round(kwh_at_month_start, 3),
            "last_month_checked": self.coordinator.last_month_checked,
            "month_start_timestamp": month_start_timestamp,
        }
        
        return round(forecast_kwh, 3)