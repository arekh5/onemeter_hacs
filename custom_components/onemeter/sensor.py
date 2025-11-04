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
PAYLOAD_PREFIX = "v1=" # Nowa stała dla prefiksu payloadu

# ----------------------------------------------------------------------
# KLASA KOORDYNATORA DANYCH (ZARZĄDZA KLIENTEM MQTT)
# ----------------------------------------------------------------------

class OneMeterCoordinator(DataUpdateCoordinator):
    """Koordynator zarządzający połączeniem MQTT i danymi."""
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        
        config = {**entry.data, **entry.options}
        
        self.device_id = "om9613"
        # MAC urządzenia OneMeter, używany do filtrowania w payloadzie GL-S10
        self.target_mac = "E58D81019613" 
        # Temat z surowymi impulsami, na który subskrybujemy (Format GL-S10)
        self.base_topic = "onemeter/s10/v1" 
        
        # --- Stan MQTT ---
        self.unsubscribe_mqtt = None

        # --- Stan Licznika (odzyskiwany na starcie) ---
        self.total_impulses = 0 
        self.last_impulse_times = deque(maxlen=2) 
        self.last_valid_power = 0.0
        
        # --- Parametry ---
        self.impulses_per_kwh = config.get("impulses_per_kwh", 1000)
        self.max_power_kw = config.get("max_power_kw", 20.0)
        self.power_timeout_seconds = config.get("power_timeout_seconds", 300)
        self.power_history = deque(maxlen=config.get("power_average_window", 2))
        
        # --- Zapisywany Stan Prognozy (Persystencja) ---
        self.kwh_at_month_start = 0.0
        self.last_month_checked = datetime.now().month
        self.month_start_timestamp = time.time()
        
        # Inicjalizacja danych na start, zostanie nadpisana przez odzyskany stan
        self.data = None
        self.last_update_success = False
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None 
        )

    async def _async_update_data(self):
        """Metoda wymagana przez DataUpdateCoordinator, ale nieużywana (dane pochodzą z MQTT)."""
        return self.data
    
    async def _async_restore_state(self, restored_kwh: float):
        """Ustawia stan początkowy Koordynatora na podstawie odzyskanego kWh z encji."""
        self.total_impulses = int(restored_kwh * self.impulses_per_kwh)
        _LOGGER.info(f"✅ Koordynator: Odzyskano stan energii: {restored_kwh} kWh (co odpowiada {self.total_impulses} impulsom).")
        
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
        
        # WERYFIKACJA ODBIORU (Wymuszamy widoczność INFO)
        _LOGGER.info(f"🚨 CALLBACK OTRZYMANY. Temat: {msg.topic}, Długość Payload: {len(msg.payload)} bytes")
        
        try:
            raw_payload_str = msg.payload.decode("utf-8")
            
            # NOWA LOGIKA: Usuwamy prefiks 'v1='
            if raw_payload_str.startswith(PAYLOAD_PREFIX):
                json_str = raw_payload_str[len(PAYLOAD_PREFIX):]
            else:
                json_str = raw_payload_str
            
            payload = json.loads(json_str)
            
            dev_list = payload.get("dev_list", [])
            
            # --- 1. Znajdź wpis dla docelowego urządzenia OneMeter w dev_list (FORMAT GL-S10) ---
            target_mac_upper = self.target_mac.upper() 
            onemeter_entry = next((
                dev for dev in dev_list if dev.get("mac", "").upper() == target_mac_upper
            ), None)
            
            if not onemeter_entry:
                _LOGGER.info(f"Odebrano wiadomość MQTT, ale nie znaleziono urządzenia OneMeter ({self.target_mac}) w 'dev_list'. Ignorowanie.")
                return

            # Timestamp jest w milisekundach (HA wymaga sekund)
            ts_ms = onemeter_entry.get("ts")
            
            if not isinstance(ts_ms, int) or ts_ms == 0:
                 _LOGGER.info("Znaleziono urządzenie, ale klucz 'ts' jest nieprawidłowy lub brak. Ignorowanie.")
                 return
                 
            # Konwersja ms na sekundy UNIX
            now = ts_ms / 1000 
            
            # W formacie GL-S10 każdy odczyt to jeden impuls
            self.total_impulses += 1 
            self.last_impulse_times.append(now) 
            _LOGGER.info(f"📥 OTRZYMANO IMPULS. Łącznie impulsów: {self.total_impulses}, czas: {now}")

            # --- 2. Obliczenie Mocy (Delta t) ---
            power_kw = 0.0
            if len(self.last_impulse_times) == 2:
                time_diff_t = self.last_impulse_times[1] - self.last_impulse_times[0]
                if time_diff_t > 0:
                    power_kw = 3600 / (self.impulses_per_kwh * time_diff_t)
                    if power_kw > self.max_power_kw:
                         # Ograniczenie do max_power_kw (bezpiecznik)
                         power_kw = self.max_power_kw
                    self.last_valid_power = power_kw
            
            self.power_history.append(self.last_valid_power)
            
            # --- 3. Obliczenie Energii i Aktualizacja HA ---
            kwh = self.total_impulses / self.impulses_per_kwh
            avg_power_kw = sum(self.power_history) / len(self.power_history)
            
            self.data = {
                "power_kw": avg_power_kw,
                "kwh": kwh,
                "last_impulse_time": now,
                "last_impulse_kw": self.last_valid_power,
            }
            self.last_update_success = True
            self.async_set_updated_data(self.data)
            _LOGGER.info(f"📊 Zaktualizowano dane HA: kWh={round(kwh, 3)}, Power={round(avg_power_kw, 3)}kW")

            # --- 4. Ponowna publikacja przetworzonych danych do MQTT ---
            timestamp_dt = datetime.fromtimestamp(now)
            timestamp_str = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            mqtt_payload = {
                "timestamp": timestamp_str,
                "impulses": self.total_impulses,
                "kwh": round(kwh, 3),
                "power_kw": round(avg_power_kw, 3),
                "forecast_kwh": 0 
            }
            
            state_topic = f"onemeter/energy/{self.device_id}/state"
            try:
                await mqtt.async_publish(
                    self.hass, 
                    state_topic, 
                    json.dumps(mqtt_payload), 
                    qos=0, 
                    retain=False
                )
                _LOGGER.info(f"📤 Opublikowano przetworzony stan na temacie: {state_topic}")
            except Exception as publish_e:
                 _LOGGER.error(f"❌ BŁĄD PUBLIKACJI: Nie udało się opublikować przetworzonego stanu na MQTT: {publish_e}")
            
        except json.JSONDecodeError as e:
            # W tym miejscu teraz logujemy błąd JSON, jeśli po usunięciu prefiksu jest nadal niepoprawny
            _LOGGER.error(f"❌ Błąd parsowania JSON wiadomości MQTT (po usunięciu prefiksu): {e}")
        except Exception as e:
            _LOGGER.error(f"❌ Błąd krytyczny przetwarzania wiadomości MQTT: {e}")

    async def async_added_to_hass(self) -> None:
        """Subskrypcja MQTT i ustawienie statusu urządzenia (po gotowości klienta)."""
        
        _LOGGER.info("🚨 ETAP 1/3: Rozpoczynanie procesu subskrypcji MQTT dla Koordynatora.")
        
        try:
            await mqtt.async_when_ready(self.hass)
            _LOGGER.info("🚨 ETAP 2/3: Klient MQTT Home Assistanta jest GOTOWY do subskrypcji.")

            self.unsubscribe_mqtt = await mqtt.async_subscribe(
                self.hass,
                self.base_topic,
                self._async_message_received,
                qos=1,
                encoding="utf-8"
            )
            
            if callable(self.unsubscribe_mqtt):
                _LOGGER.info(f"✅ ETAP 3/3: Subskrypcja tematu {self.base_topic} jest AKTYWNA. Funkcja callbacku działa.")
            else:
                 _LOGGER.error(f"❌ ETAP 3/3: Subskrypcja tematu {self.base_topic} NIEUDANA. Zwrócona wartość: {self.unsubscribe_mqtt}")

            status_topic = f"onemeter/energy/{self.device_id}/status"
            await mqtt.async_publish(
                self.hass, 
                status_topic, 
                "online", 
                qos=1, 
                retain=True
            )
            _LOGGER.info(f"✅ Opublikowano status 'online' na temacie: {status_topic}")

        except Exception as e:
            _LOGGER.error(f"🚨 BŁĄD KRYTYCZNY SUBKSKRYPCJI: Wystąpił błąd w async_added_to_hass: {e}")

        await super().async_added_to_hass()
        
    async def async_will_remove_from_hass(self) -> None:
        """Usuwanie subskrypcji i statusu offline."""
        status_topic = f"onemeter/energy/{self.device_id}/status"
        try:
            await mqtt.async_publish(
                self.hass, 
                status_topic, 
                "offline", 
                qos=1, 
                retain=True
            )
            _LOGGER.info(f"🚪 Opublikowano status 'offline' na temacie: {status_topic}")
        except Exception as e:
            _LOGGER.error(f"❌ Nie udało się opublikować statusu MQTT 'offline': {e}")
        
        if self.unsubscribe_mqtt:
            self.unsubscribe_mqtt()
        await super().async_will_remove_from_hass()

# ----------------------------------------------------------------------
# ASYNCHRONICZNE SETUP (TWORZENIE ENCJACH - DLA POPRAWKI BŁĘDU SETUP)
# ----------------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Tworzenie encji sensorów z obsługą odzyskiwania stanu Koordynatora."""
    
    coordinator = OneMeterCoordinator(hass, entry)

    # 1. Odzyskujemy stan kWh 
    entity_id_to_restore = f"sensor.{coordinator.device_id}_energy_kwh"
    last_state = hass.states.get(entity_id_to_restore)
    
    restored_kwh = 0.0
    if last_state and last_state.state:
        try:
            restored_kwh = float(last_state.state)
            _LOGGER.info(f"✅ Odzyskano ostatni stan sensora {entity_id_to_restore}: {restored_kwh} kWh.")
        except ValueError:
            _LOGGER.warning(f"Nie udało się odzyskać stanu: Nieprawidłowa wartość '{last_state.state}'. Używam 0.0 kWh.")

    # 2. Inicjalizujemy Koordynatora odzyskanym stanem
    await coordinator._async_restore_state(restored_kwh)
    
    # 🚨 KRYTYCZNA AKTYWACJA
    await coordinator.async_config_entry_first_refresh()
    
    # 3. Dodajemy Koordynatora do HA
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
    
    # Nowa linia: Wymaga, aby klasy dziedziczące definiowały translation_key
    _attr_translation_key: str 

    def __init__(self, coordinator: OneMeterCoordinator):
        self.coordinator = coordinator
        
        # Używamy translation_key, który jest zdefiniowany w klasach dziedziczących
        # Musimy go użyć do stworzenia unikalnego ID
        self._attr_unique_id = f"{coordinator.device_id}_{self._attr_translation_key}"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="OneMeter",
            manufacturer="OneMeter",
            model="Energy Meter",
            sw_version="2.0.29",
        )

    @property
    def available(self) -> bool:
        """Zwraca True, jeśli koordynator ma dane."""
        # Wystarczy sprawdzić, czy Koordynator się uruchomił
        return callable(self.coordinator.unsubscribe_mqtt)

    async def async_added_to_hass(self) -> None:
        """Rejestracja callbacku po dodaniu encji."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
        await super().async_added_to_hass()

class OneMeterEnergySensor(OneMeterBaseSensor, RestoreEntity):
    """Sensor energii (kWh), który odzyskuje stan (persistence)."""
    # Definicja atrybutów (w tym translation_key, który jest używany w BaseSensor)
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
    # Definicja atrybutów
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "power_kw"

    @property
    def native_value(self) -> StateType:
        """Zwraca obecną wartość mocy w kW."""
        if self.coordinator.data is not None:
            time_since_impulse = time.time() - self.coordinator.data.get("last_impulse_time", 0)
            
            # Weryfikacja timeoutu (zerowanie mocy, jeśli zbyt długo nie ma impulsu)
            if time_since_impulse > self.coordinator.power_timeout_seconds:
                 return 0.0
                 
            return round(self.coordinator.data.get("power_kw", 0.0), 3)
        return None

class OneMeterForecastSensor(OneMeterBaseSensor, RestoreEntity):
    """Sensor prognozy miesięcznego zużycia (kWh)."""
    # Definicja atrybutów
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "forecast_kwh"

    @property
    def native_value(self) -> StateType:
        """Oblicza i zwraca prognozę."""
        forecast_kwh = 0.0
        
        if self.coordinator.data is None:
            return None
            
        # ... (Logika prognozy jest pominięta dla zwięzłości, ale musi być poprawna)
        kwh = self.coordinator.data.get("kwh", 0.0)
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
        
        # Zapisz stan do atrybutów dla persystencji
        self._attr_extra_state_attributes = {
            "kwh_at_month_start": round(self.coordinator.kwh_at_month_start, 3),
            "last_month_checked": self.coordinator.last_month_checked,
            "month_start_timestamp": self.coordinator.month_start_timestamp,
        }
        
        return round(forecast_kwh, 3)