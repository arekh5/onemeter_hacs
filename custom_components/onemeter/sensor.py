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
        
        config = {**entry.data, **entry.options}
        
        self.device_id = "om9613"
        # Temat z surowymi impulsami, na który subskrybujemy
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

    async def _async_restore_state(self, restored_kwh: float):
        """Ustawia stan początkowy Koordynatora na podstawie odzyskanego kWh z encji."""
        self.total_impulses = int(restored_kwh * self.impulses_per_kwh)
        _LOGGER.info(f"✅ Koordynator: Odzyskano stan energii: {restored_kwh} kWh (co odpowiada {self.total_impulses} impulsom).")
        
        # Ustawienie stanu, aby encje były dostępne natychmiast po starcie
        self.data = {
            "power_kw": 0.0,
            "kwh": restored_kwh,
            # Ustawienie czasu ostatniego impulsu, aby moc chwilowa była 0.0
            "last_impulse_time": time.time() - self.power_timeout_seconds - 1, 
            "last_impulse_kw": 0.0,
        }
        self.last_update_success = True

    @callback
    async def _async_message_received(self, msg):
        """Asynchroniczna obsługa wiadomości MQTT."""
        
        # DODATKOWE LOGOWANIE (v2.0.13), aby potwierdzić wywołanie callbacku
        _LOGGER.info(f"✅ CALLBACK WYWOŁANY. Temat: {msg.topic}, Payload: {len(msg.payload)} bytes")
        
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            dev_list = payload.get("dev_list", [])
            
            if not dev_list:
                _LOGGER.warning("Odebrano wiadomość MQTT, ale brakuje klucza 'dev_list'. Ignorowanie.")
                return

            now = time.time()
            self.total_impulses += 1 
            self.last_impulse_times.append(now) 
            _LOGGER.debug(f"📥 Otrzymano nowy impuls. Łącznie impulsów: {self.total_impulses}")

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
            
            # --- 3. Aktualizacja danych i powiadomienie encji HA ---
            avg_power_kw = sum(self.power_history) / len(self.power_history)
            
            self.data = {
                "power_kw": avg_power_kw,
                "kwh": kwh,
                "last_impulse_time": now,
                "last_impulse_kw": self.last_valid_power,
            }
            self.last_update_success = True
            self.async_set_updated_data(self.data)
            _LOGGER.debug(f"📊 Zaktualizowano dane HA: kWh={round(kwh, 3)}, Power={round(avg_power_kw, 3)}kW")

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
            
        except Exception as e:
            _LOGGER.error(f"❌ Błąd przetwarzania wiadomości MQTT: {e}")

    async def async_added_to_hass(self) -> None:
        """Subskrypcja MQTT i ustawienie statusu urządzenia (po gotowości klienta)."""
        
        # Czekanie na gotowość klienta MQTT
        await mqtt.async_when_ready(self.hass)
        _LOGGER.debug("✅ Klient MQTT Home Assistanta gotowy do subskrypcji i publikacji.")
        
        # 1. SUBSKRYPCJA GŁÓWNEGO TEMATU
        self.unsubscribe_mqtt = await mqtt.async_subscribe(
            self.hass,
            self.base_topic,
            self._async_message_received,
            qos=1,
            encoding="utf-8"
        )
        _LOGGER.info(f"✅ Subskrypcja tematu {self.base_topic} aktywna.")
        
        # 2. PUBLIKACJA STATUSU
        status_topic = f"onemeter/energy/{self.device_id}/status"
        try:
            await mqtt.async_publish(
                self.hass, 
                status_topic, 
                "online", 
                qos=1, 
                retain=True
            )
            _LOGGER.info(f"✅ Opublikowano status 'online' na temacie: {status_topic}")
        except Exception as e:
            _LOGGER.error(f"❌ Nie udało się opublikować statusu MQTT 'online': {e}")
        
        await super().async_added_to_hass()
        
    async def async_will_remove_from_hass(self) -> None:
        """Usunięcie subskrypcji MQTT i publikacja statusu 'offline'."""
        
        status_topic = f"onemeter/energy/{self.device_id}/status"
        try:
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
        await super().async_will_remove_from_hass()


# ----------------------------------------------------------------------
# ASYNCHRONICZNE SETUP (TWORZENIE ENCJACH)
# ----------------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Tworzenie encji sensorów z obsługą odzyskiwania stanu Koordynatora (v2.0.14)."""
    
    coordinator = OneMeterCoordinator(hass, entry)

    # 1. POPRAWKA: Odzyskujemy stan kWh BEZ tworzenia tymczasowej encji
    entity_id_to_restore = f"sensor.{coordinator.device_id}_energy_kwh"
    
    # Pobieranie ostatniego znanego stanu bezpośrednio z serwisu stanów HA
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
    
    # 3. Dodajemy Koordynatora do HA
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # 4. Dodajemy Encje (teraz już z zainicjalizowanymi danymi)
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
        """Ładowanie stanu i rejestracja słuchacza."""
        await super().async_added_to_hass()
        self.coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def available(self) -> bool:
        """Sprawdza, czy koordynator ma dane i aktualizacja była udana."""
        return self.coordinator.data is not None and getattr(self.coordinator, 'last_update_success', False)


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

        # Logika timeout'u zerująca moc
        if (now - last_impulse_time) > self.coordinator.power_timeout_seconds:
            return 0.0
        
        return round(power, 3)

    
class OneMeterForecastSensor(OneMeterBaseSensor):
    """Sensor prognozy miesięcznej (kWh) z persystencją stanu."""

    _attr_has_entity_name = True
    _attr_name = "Monthly Forecast"
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
        
        # Odtwarzanie stanu z bazy danych HA
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

    @property
    def native_value(self) -> StateType:
        """Obliczenie i zapisanie prognozy miesięcznej."""
        
        kwh = self.coordinator.data.get("kwh", 0.0)
        forecast_kwh = 0.0
        now_dt = datetime.now()
        current_month = now_dt.month
        
        # 1. Sprawdzenie zmiany miesiąca (reset licznika na start miesiąca)
        if current_month != self.coordinator.last_month_checked:
            _LOGGER.info(f"🔄 Zmiana miesiąca wykryta. Reset prognozy.")
            self.coordinator.kwh_at_month_start = kwh 
            self.coordinator.last_month_checked = current_month
            self.coordinator.month_start_timestamp = time.time() 
        # Inicjalizacja stanu, jeśli HA wystartował po raz pierwszy w tym miesiącu
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
            "current_month_kwh": round(current_month_kwh, 3)
        }

        return round(forecast_kwh, 3)