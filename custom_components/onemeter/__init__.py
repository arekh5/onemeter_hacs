from homeassistant.core import HomeAssistant

DOMAIN = "onemeter"

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    from .sensor import OneMeterSensor
    hass.data[DOMAIN]["entry"] = entry
    hass.async_create_task(
        OneMeterSensor(hass, entry).async_start()
    )
    return True
