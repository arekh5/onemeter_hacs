import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD

DOMAIN = "onemeter"

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT, default=1883): int,
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Required("device_name", default="OneMeter"): str,
    vol.Optional("window_seconds", default=60): int,
    vol.Optional("max_power_kw", default=20.0): float,
})


class OneMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OneMeter."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input["device_name"], data=user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
