import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

DOMAIN = "onemeter"

class OneMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Konfiguracja integracji OneMeter"""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Tworzy wpis konfiguracyjny z tylko potrzebnymi danymi
            return self.async_create_entry(title="OneMeter", data=user_input)

        schema = vol.Schema({
            # Zbieramy tylko parametry licznika. Dane MQTT są pobierane z globalnego brokera HA.
            vol.Optional("impulses_per_kwh", default=1000): int,
            vol.Optional("max_power_kw", default=20): int,
            vol.Optional("power_average_window", default=2): int,
            vol.Optional("power_timeout_seconds", default=300): int,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OneMeterOptionsFlowHandler(config_entry)


class OneMeterOptionsFlowHandler(config_entries.OptionsFlow):
    """Edycja ustawień integracji OneMeter."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Zapisuje nowe opcje
            return self.async_create_entry(title="", data=user_input)

        # Łączymy data i options
        current = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema({
            # Edytujemy tylko parametry licznika
            vol.Optional("impulses_per_kwh", default=current.get("impulses_per_kwh", 1000)): int,
            vol.Optional("max_power_kw", default=current.get("max_power_kw", 20)): int,
            vol.Optional("power_average_window", default=current.get("power_average_window", 2)): int,
            vol.Optional("power_timeout_seconds", default=current.get("power_timeout_seconds", 300)): int,
        })

        return self.async_show_form(step_id="init", data_schema=schema)