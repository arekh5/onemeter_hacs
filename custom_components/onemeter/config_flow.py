import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

DOMAIN = "onemeter"

# Stałe konfiguracji
CONF_DEVICE_ID = "device_id"
CONF_MAC = "mac"
CONF_TOPIC = "topic"
CONF_TIMEOUT = "power_timeout_seconds"
CONF_INITIAL_KWH = "initial_kwh"
CONF_IMPULSES_PER_KWH = "impulses_per_kwh"
CONF_MAX_POWER_KW = "max_power_kw"
CONF_POWER_AVERAGE_WINDOW = "power_average_window"
CONF_MONTHLY_USAGE_KWH = "monthly_usage_kwh"  # 🆕 Nowe pole

# --- Krok 1: Identyfikacja i MQTT ---
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID, default="om9613"): str,
        vol.Required(CONF_MAC, default="E58D81019613"): str,
        vol.Required(CONF_TOPIC, default="onemeter/s10/v1"): str,
        vol.Required(CONF_INITIAL_KWH, default=0.0): vol.Coerce(float),
        vol.Required(CONF_MONTHLY_USAGE_KWH, default=0.0): vol.Coerce(float),
    }
)

# --- Krok 2: Ustawienia techniczne licznika ---
STEP_METER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IMPULSES_PER_KWH, default=1000): vol.Coerce(int),
        vol.Required(CONF_MAX_POWER_KW, default=20): vol.Coerce(int),  # 🔧 teraz int
        vol.Required(CONF_POWER_AVERAGE_WINDOW, default=2): vol.Coerce(int),
        vol.Required(CONF_TIMEOUT, default=300): vol.Coerce(int),
    }
)


class OneMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Kreator konfiguracji OneMeter."""

    VERSION = 1
    temp_data = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()
            self.temp_data.update(user_input)
            return await self.async_step_meter()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_meter(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            self.temp_data.update(user_input)
            if user_input.get(CONF_IMPULSES_PER_KWH) <= 0:
                errors[CONF_IMPULSES_PER_KWH] = "invalid_impulses"

            if not errors:
                title = f"OneMeter ({self.temp_data[CONF_DEVICE_ID]})"
                return self.async_create_entry(title=title, data=self.temp_data)

        return self.async_show_form(
            step_id="meter", data_schema=STEP_METER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OneMeterOptionsFlowHandler(config_entry)


class OneMeterOptionsFlowHandler(config_entries.OptionsFlow):
    """Opcje konfiguracji OneMeter (edycja ustawień)."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema(
            {
                vol.Optional(CONF_INITIAL_KWH, default=current.get(CONF_INITIAL_KWH, 0.0)): vol.Coerce(float),
                vol.Optional(CONF_MONTHLY_USAGE_KWH, default=current.get(CONF_MONTHLY_USAGE_KWH, 0.0)): vol.Coerce(float),
                vol.Optional(CONF_IMPULSES_PER_KWH, default=current.get(CONF_IMPULSES_PER_KWH, 1000)): vol.Coerce(int),
                vol.Optional(CONF_MAX_POWER_KW, default=current.get(CONF_MAX_POWER_KW, 20)): vol.Coerce(int),  # 🔧 int
                vol.Optional(CONF_POWER_AVERAGE_WINDOW, default=current.get(CONF_POWER_AVERAGE_WINDOW, 2)): vol.Coerce(int),
                vol.Optional(CONF_TIMEOUT, default=current.get(CONF_TIMEOUT, 300)): vol.Coerce(int),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
