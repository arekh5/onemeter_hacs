import voluptuous as vol
from homeassistant import config_entries
from . import DOMAIN

class OneMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="OneMeter OM9613", data=user_input)

        schema = vol.Schema({
            vol.Required("mqtt_broker", default="localhost"): str,
            vol.Required("mqtt_port", default=1883): int,
            vol.Required("mqtt_user", default="mqtt"): str,
            vol.Required("mqtt_pass", default="mqtt"): str,
            vol.Optional("max_power_kw", default=20.0): float,
            vol.Optional("window_seconds", default=60): int
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
