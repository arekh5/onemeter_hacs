import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "onemeter"
PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Inicjalizacja integracji OneMeter."""
    
    # Dodanie platformy sensorów
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Usunięcie integracji."""
    
    # Rozładowanie platformy sensorów
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    return unload_ok