from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DOMAIN


class PIDClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=user_input["name"],
                data=user_input,
            )

        schema = {
            "name": selector.TextSelector(),
            "temperature_entity_id": selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        }

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )
