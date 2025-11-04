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
            return self.async_create_entry(title="OneMeter", data=user_input)

        # Ustawienia domyślne dla nowej konfiguracji
        schema = vol.Schema({
            # Parametry MQTT (teoretycznie do usunięcia, ale zachowane na razie)
            vol.Required("mqtt_broker", default="127.0.0.1"): str,
            vol.Required("mqtt_port", default=1883): int,
            vol.Required("mqtt_user", default="mqtt"): str,
            # POPRAWKA: Usunięcie błędu składni (z poprzednich wersji)
            vol.Required("mqtt_pass", default="mqtt"): str,
            
            # Właściwe parametry licznika
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
    """Edycja ustawień integracji OneMeter (Options Flow)."""

    def __init__(self, config_entry):
        """Inicjalizacja Options Flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Zarządzanie opcjami."""
        if user_input is not None:
            # Aktualizacja opcji (kluczowe do zapisu zmian)
            return self.async_create_entry(title="", data=user_input)

        # Pobieramy bieżące dane i opcje, aby wypełnić formularz
        current = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema({
            # Parametry MQTT
            vol.Required("mqtt_broker", default=current.get("mqtt_broker", "127.0.0.1")): str,
            vol.Required("mqtt_port", default=current.get("mqtt_port", 1883)): int,
            vol.Required("mqtt_user", default=current.get("mqtt_user", "mqtt")): str,
            # POPRAWKA: Usunięcie błędu składni (z poprzednich wersji)
            vol.Required("mqtt_pass", default=current.get("mqtt_pass", "mqtt")): str,
            # Parametry licznika
            vol.Optional("impulses_per_kwh", default=current.get("impulses_per_kwh", 1000)): int,
            vol.Optional("max_power_kw", default=current.get("max_power_kw", 20)): int,
            vol.Optional("power_average_window", default=current.get("power_average_window", 2)): int,
            vol.Optional("power_timeout_seconds", default=current.get("power_timeout_seconds", 300)): int,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema
        )