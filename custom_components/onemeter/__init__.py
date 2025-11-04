import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"] 

async def async_setup_entry(hass, entry):
    """Konfiguruje integrację OneMeter jako wpis konfiguracyjny."""
    
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    
    return True

async def async_unload_entry(hass, entry):
    """Usuwa integrację OneMeter."""
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok and entry.entry_id in hass.data.get("onemeter", {}):
        hass.data["onemeter"].pop(entry.entry_id)
        
    return unload_ok