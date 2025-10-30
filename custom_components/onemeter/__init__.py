import asyncio
import logging
from .sensor import OneMeterSensorAsync  # import klasy sensora

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    """Konfiguracja po dodaniu entry w HA"""
    _LOGGER.info("Uruchamianie OneMeter Sensor")
    
    # Tworzymy instancję sensora
    sensor = OneMeterSensorAsync(hass, entry)
    
    # Uruchamiamy klienta MQTT asynchronicznie
    await sensor.start()
    
    # Można zachować referencję w hass.data jeśli potrzebne później
    hass.data.setdefault("onemeter", {})[entry.entry_id] = sensor
    
    return True

async def async_unload_entry(hass, entry):
    """Odinstalowanie entry"""
    sensor = hass.data.get("onemeter", {}).pop(entry.entry_id, None)
    if sensor and sensor.client:
        sensor.client.loop_stop()
        sensor.client.disconnect()
    return True
