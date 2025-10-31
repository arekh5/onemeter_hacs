import logging
from .sensor import OneMeterSensor

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    """Inicjalizacja integracji OneMeter"""
    _LOGGER.info("🔌 Uruchamianie OneMeter Sensor")
    
    sensor = OneMeterSensor(hass, entry)
    await hass.async_add_executor_job(sensor.start)
    
    hass.data.setdefault("onemeter", {})[entry.entry_id] = sensor
    return True

async def async_unload_entry(hass, entry):
    """Usunięcie integracji"""
    sensor = hass.data.get("onemeter", {}).pop(entry.entry_id, None)
    if sensor:
        sensor.stop()
    return True
