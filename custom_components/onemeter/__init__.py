import logging

_LOGGER = logging.getLogger(__name__)

# Rejestrujemy platformę 'sensor'
PLATFORMS = ["sensor"] 

async def async_setup_entry(hass, entry):
    """Konfiguruje integrację OneMeter jako wpis konfiguracyjny."""
    
    # Przekazujemy konfigurację do platformy 'sensor', gdzie jest właściwy kod inicjalizacyjny
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass, entry):
    """Usuwa integrację OneMeter."""
    
    # Odładowujemy platformę 'sensor'
    return await hass.config_entries.async_unload_entry(entry, PLATFORMS)