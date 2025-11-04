import logging

_LOGGER = logging.getLogger(__name__)

# Rejestrujemy platformę 'sensor'
PLATFORMS = ["sensor"] 
DOMAIN = "onemeter"

async def async_setup_entry(hass, entry):
    """Konfiguruje integrację OneMeter jako wpis konfiguracyjny."""
    
    # ✅ POPRAWKA: Używamy poprawnej funkcji async_forward_entry_setups (z literą 's' na końcu)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass, entry):
    """Usuwa integrację OneMeter."""
    
    # Używamy async_unload_platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Opcjonalnie usuwamy Koordynatora z hass.data
    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unload_ok