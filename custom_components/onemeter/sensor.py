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
from homeassistant.helpers.restore_state import RestoreEntity # ✅ DODANE
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
CONF_MONTHLY_USAGE_KWH = "monthly_usage_kwh" # ✅ UJEDNOLICONE

# ----------------------------------------------------------------------
# KOORDYNATOR – zarządza MQTT i logiką
# ----------------------------------------------------------------------

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
        self.max_power_kw = int(config.get(CONF_MAX_POWER_KW, 20))
        self.power_timeout_seconds = config.get(CONF_TIMEOUT, 300)
        self.power_history = deque(maxlen=config.get(CONF_POWER_AVERAGE_WINDOW, 2))
        self.initial_kwh_setting = config.get(CONF_INITIAL_KWH, 0.0)
        self.monthly_usage_kwh = config.get(CONF_MONTHLY_USAGE_KWH, 0.0)

        # Stany: Inicjalizacja na 0, zostaną ustalone przez async_init_states
        self.total_impulses: int = 0
        self.kwh_at_month_start: int = 0
        self.last_month_checked = datetime.now().month
        self.month_start_timestamp = time.time()
        self.last_valid_power = 0.0
        self.last_impulse_times = deque(maxlen=2)
        self.unsubscribe_mqtt = None
        self.data = None

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=1))

    async def async_init_states(self, restored_kwh: float):
        """Ustawia stan początkowy (na podstawie przywróconego stanu HA lub konfiguracji)."""

        self.total_impulses = int(restored_kwh * self.impulses_per_kwh)
        _LOGGER.info(f"✅ Ustawiono stan: {restored_kwh} kWh ({self.total_impulses} imp.)")

        # Obliczenie punktu startowego miesiąca
        # Baza miesięczna = Całkowite zużycie (imp) - zużycie tego miesiąca (imp)
        initial_month_imp = int(self.monthly_usage_kwh * self.impulses_per_kwh)
        self.kwh_at_month_start = self.total_impulses - initial_month_imp
        
        _LOGGER.info(
            f"📅 Start miesiąca ustawiony na: {self.kwh_at_month_start} imp (początkowe zużycie tego miesiąca: {self.monthly_usage_kwh} kWh)"
        )

        # Ustawienie początku miesiąca na 1. dzień bieżącego miesiąca
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1, 0, 0, 0)
        self.month_start_timestamp = month_start.timestamp()

        # Inicjalizacja danych
        self.data = {
            "power_kw": 0.0,
            "kwh": restored_kwh,
            "last_impulse_time": time.time() - self.power_timeout_seconds - 1,
            "last_impulse_kw": 0.0,
        }

    async def _async_update_data(self):
        """Aktualizuje dane co 60 minut. Używane do odświeżenia prognozy."""
        if self.data is None:
            # Powinno być już zainicjalizowane przez async_init_states, ale na wszelki wypadek
            await self.async_init_states(self.total_impulses / self.impulses_per_kwh)
            
        self.async_set_updated_data(self.data)
        return self.data

    @callback
    async def _async_message_received(self, msg):
        """Obsługuje wiadomości MQTT (Impulsy)."""
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
            
            # Obliczanie mocy chwilowej
            power_kw = 0.0
            if len(self.last_impulse_times) == 2:
                dt = self.last_impulse_times[1] - self.last_impulse_times[0]
                if dt > 0:
                    power_kw = min(3600 / (self.impulses_per_kwh * dt), self.max_power_kw)
                    self.last_valid_power = power_kw
                    
            self.power_history.append(self.last_valid_power)
            
            # Obliczenie KWH i aktualizacja danych
            kwh = self.total_impulses / self.impulses_per_kwh
            avg_power = sum(self.power_history) / len(self.power_history)
            
            self.data = {
                "power_kw": avg_power,
                "kwh": kwh,
                "last_impulse_time": now,
            }
            self.async_set_updated_data(self.data)
            
            # Zapewnienie, że reset miesięczny jest sprawdzany przy każdym impulsie
            now_dt = datetime.fromtimestamp(now)
            if now_dt.month != self.last_month_checked:
                self.kwh_at_month_start = self.total_impulses
                self.month_start_timestamp = now
                self.last_month_checked = now_dt.month

        except Exception as e:
            _LOGGER.error(f"Błąd MQTT: {e}")

    async def async_added_to_hass(self) -> None:
        """Subskrypcja MQTT."""
        try:
            self.unsubscribe_mqtt = await mqtt.async_subscribe(
                self.hass, self.base_topic, self._async_message_received, qos=1, encoding="utf-8"
            )
            await mqtt.async_publish(
                self.hass, f"onemeter/energy/{self.device_id}/status", "online", qos=1, retain=True
            )
        except Exception as e:
            _LOGGER.error(f"❌ Błąd subskrypcji MQTT: {e}")

    async def async_will_remove_from_hass(self) -> None:
        """Usuwanie subskrypcji i publikacja statusu offline."""
        try:
            await mqtt.async_publish(
                self.hass, f"onemeter/energy/{self.device_id}/status", "offline", qos=1, retain=True
            )
        except Exception as e:
            _LOGGER.error(f"❌ Nie udało się opublikować 'offline': {e}")
        if self.unsubscribe_mqtt:
            self.unsubscribe_mqtt()


# ----------------------------------------------------------------------
# ASYNC SETUP ENTRY
# ----------------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = OneMeterCoordinator(hass, entry)
    
    # 1. PRZYWRACANIE STANU Z HA DLA LICZNIKA KWH
    entity_id = f"sensor.{coordinator.device_id}_energy_kwh"
    last_state = hass.states.get(entity_id)
    restored_kwh = float(coordinator.initial_kwh_setting)

    if last_state and last_state.state:
        try:
            restored_kwh = float(last_state.state)
            _LOGGER.info(f"✅ Odzyskano stan {entity_id}: {restored_kwh} kWh.")
        except ValueError:
            pass

    # 2. INICJALIZACJA KOORDYNATORA ODCZYTANYM STANEM
    await coordinator.async_init_states(restored_kwh)
    await coordinator.async_added_to_hass()
    await coordinator.async_config_entry_first_refresh() # Wymusza pierwsze odświeżenie danych

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async_add_entities([
        OneMeterEnergySensor(coordinator),
        OneMeterPowerSensor(coordinator),
        OneMeterForecastSensor(coordinator),
    ])
    return True

# ----------------------------------------------------------------------
# ENTCJE SENSORÓW
# ----------------------------------------------------------------------

class OneMeterBaseSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: OneMeterCoordinator):
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.device_id}_{self._attr_translation_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="OneMeter",
            manufacturer="OneMeter",
            model="Energy Meter",
            sw_version="2.1.1",
        )
    
    async def async_added_to_hass(self) -> None:
        """Dodanie słuchacza do koordynatora."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
        await super().async_added_to_hass()


class OneMeterEnergySensor(OneMeterBaseSensor, RestoreEntity): # ✅ DODANO RestoreEntity
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
        # Zerowanie mocy, jeśli ostatni impuls był zbyt dawno
        if time.time() - self.coordinator.data.get("last_impulse_time", 0) > self.coordinator.power_timeout_seconds:
            return 0.0
        return round(self.coordinator.data.get("power_kw", 0.0), 3)


class OneMeterForecastSensor(OneMeterBaseSensor, RestoreEntity): # ✅ DODANO RestoreEntity
    _attr_translation_key = "monthly_forecast_kwh"
    _attr_name = "Prognoza miesięczna"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    def __init__(self, coordinator: OneMeterCoordinator):
        super().__init__(coordinator)
        self._restored_value: StateType = None

    async def async_added_to_hass(self) -> None:
        """Odzyskanie ostatniego stanu prognozy po restarcie HA."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state:
            try:
                self._restored_value = round(float(last_state.state), 1)
            except ValueError:
                self._restored_value = 0.0
        self.async_write_ha_state()

    @property
    def native_value(self):
        if not self.coordinator.data:
            return self._restored_value
        
        now = datetime.now()
        
        # Czas, który upłynął od początku miesiąca
        elapsed_days = (time.time() - self.coordinator.month_start_timestamp) / 86400
        
        # Zużycie od początku miesiąca
        used = (self.coordinator.total_impulses - self.coordinator.kwh_at_month_start) / self.coordinator.impulses_per_kwh
        
        forecast = 0.0
        if elapsed_days > 0 and used > 0:
            days_in_month = monthrange(now.year, now.month)[1]
            forecast = (used / elapsed_days) * days_in_month
            
        self._attr_extra_state_attributes = {
            "kwh_at_month_start_imp": self.coordinator.kwh_at_month_start,
            "month_start_timestamp": self.coordinator.month_start_timestamp,
        }
        
        # Zapisanie obliczonej wartości, aby była dostępna po restarcie
        self._restored_value = round(forecast, 1)
        return self._restored_value