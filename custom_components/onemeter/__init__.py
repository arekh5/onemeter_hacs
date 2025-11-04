import logging

_LOGGER = logging.getLogger(__name__)

# Rejestrujemy platformę 'sensor'
PLATFORMS = ["sensor"] 

async def async_setup_entry(hass, entry):
    """Konfiguruje integrację OneMeter jako wpis konfiguracyjny."""
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass, entry):
    """Usuwa integrację OneMeter."""
    
    # KRYTYCZNA POPRAWKA: Używamy async_unload_platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Opcjonalnie usuwamy Koordynatora z hass.data
    if unload_ok and entry.entry_id in hass.data.get("onemeter", {}):
        hass.data["onemeter"].pop(entry.entry_id)
        
    return unload_ok