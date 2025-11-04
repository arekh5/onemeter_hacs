import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "onemeter"
PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Inicjalizacja integracji OneMeter. Ładuje platformę sensorów."""
    
    # Przekazanie ustawień do platformy 'sensor'
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Usunięcie integracji. Rozładowuje platformę sensorów."""
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Czyścimy dane z hass.data
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok