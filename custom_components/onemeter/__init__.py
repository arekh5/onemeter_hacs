import logging
from .sensor import OneMeterSensor # import klasy sensora

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    """Konfiguracja po dodaniu entry w HA"""
    _LOGGER.info("Uruchamianie OneMeter Sensor")
    
    sensor = OneMeterSensor(hass, entry)
    
    # Uruchom klienta MQTT asynchronicznie
    await sensor.start()
    
    # Zachowaj referencję w hass.data
    hass.data.setdefault("onemeter", {})[entry.entry_id] = sensor
    
    return True

async def async_unload_entry(hass, entry):
    """Odinstalowanie entry"""
    sensor = hass.data.get("onemeter", {}).pop(entry.entry_id, None)
    if sensor and sensor.client:
        sensor.client.loop_stop()
        sensor.client.disconnect()
    return True
