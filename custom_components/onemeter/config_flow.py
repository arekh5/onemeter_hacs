import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

DOMAIN = "onemeter"

class OneMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Konfiguracja GUI dla OneMeter Sensor"""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Pierwszy krok konfiguracji przez użytkownika"""
        errors = {}

        if user_input is not None:
            # Walidacja pól (opcjonalnie)
            try:
                # np. sprawdzenie portu jako liczba
                mqtt_port = int(user_input["mqtt_port"])
            except ValueError:
                errors["mqtt_port"] = "invalid_port"
            else:
                return self.async_create_entry(title="OneMeter", data=user_input)

        # Formularz konfiguracji
        data_schema = vol.Schema({
            vol.Required("mqtt_broker", default="localhost"): str,
            vol.Required("mqtt_port", default=1883): int,
            vol.Required("mqtt_user", default=""): str,
            vol.Required("mqtt_pass", default=""): str,
            vol.Optional("window_seconds", default=60): int,
            vol.Optional("max_power_kw", default=20.0): float,
            vol.Optional("heartbeat_interval", default=30): int
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
