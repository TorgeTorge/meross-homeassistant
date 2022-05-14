import logging
from typing import Optional, List, Dict

from meross_iot.controller.subdevice import Mts100v3Valve
from meross_iot.manager import MerossManager
from meross_iot.model.enums import ThermostatV3Mode
from meross_iot.model.http.device import HttpDeviceInfo

# Conditional import for switch device
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate import SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE, HVACMode.OFF, \
    HVACMode.HEAT
from homeassistant.components.climate.const import HVACMode.AUTO, HVACMode.COOL, HVACAction.IDLE, HVACMode.HEAT, \
    HVACMode.OFF, HVACMode.COOL
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, HA_CLIMATE, DEVICE_LIST_COORDINATOR)

_LOGGER = logging.getLogger(__name__)


class ValveEntityWrapper(MerossDevice, ClimateEntity):
    """Wrapper class to adapt the Meross devices into the Homeassistant platform"""
    _device: Mts100v3Valve

    def __init__(self,
                 channel: int,
                 device: Mts100v3Valve,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_CLIMATE)

        # For now, we assume that every Meross Thermostat supports the following modes.
        # This might be improved in the future by looking at the device abilities via get_abilities()
        self._flags = 0
        self._flags |= SUPPORT_TARGET_TEMPERATURE
        self._flags |= SUPPORT_PRESET_MODE

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        # Turn on the device if not already on
        if hvac_mode == HVACMode.OFF:
            await self._device.async_turn_off(skip_rate_limits=True)
            return
        elif not self._device.is_on():
            await self._device.async_turn_on(skip_rate_limits=True)

        if hvac_mode == HVACMode.HEAT:
            await self._device.async_set_mode(ThermostatV3Mode.HEAT, skip_rate_limits=True)
        elif hvac_mode == HVACMode.AUTO:
            await self._device.async_set_mode(ThermostatV3Mode.AUTO, skip_rate_limits=True)
        elif hvac_mode == HVACMode.COOL:
            await self._device.async_set_mode(ThermostatV3Mode.COOL, skip_rate_limits=True)
        else:
            _LOGGER.warning(f"Unsupported mode for this device ({self.name}): {hvac_mode}")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._device.async_set_mode(ThermostatV3Mode[preset_mode], skip_rate_limits=True)

    async def async_set_temperature(self, **kwargs):
        target = kwargs.get('temperature')
        await self._device.async_set_target_temperature(target, skip_rate_limits=True)

    @property
    def temperature_unit(self) -> str:
        # TODO: Check if there is a way for retrieving the Merasurement Unit from the library
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> Optional[float]:
        return self._device.last_sampled_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        return self._device.target_temperature

    @property
    def target_temperature_step(self) -> Optional[float]:
        return 0.5

    @property
    def max_temp(self) -> Optional[float]:
        return self._device.max_supported_temperature

    @property
    def min_temp(self) -> Optional[float]:
        return self._device.min_supported_temperature

    @property
    def hvac_mode(self) -> str:
        if not self._device.is_on():
            return HVACMode.OFF
        elif self._device.mode == ThermostatV3Mode.AUTO:
            return HVACMode.AUTO
        elif self._device.mode == ThermostatV3Mode.HEAT:
            return HVACMode.HEAT
        elif self._device.mode == ThermostatV3Mode.COOL:
            return HVACMode.COOL
        elif self._device.mode == ThermostatV3Mode.ECONOMY:
            return HVACMode.AUTO
        elif self._device.mode == ThermostatV3Mode.CUSTOM:
            if self._device.last_sampled_temperature < self._device.target_temperature:
                return HVACMode.HEAT
            else:
                return HVACMode.COOL
        else:
            raise ValueError("Unsupported thermostat mode reported.")

    @property
    def hvac_action(self) -> Optional[str]:
        if not self._device.is_on():
            return HVACAction.OFF
        elif self._device.is_heating:
            return HVACAction.HEATING
        elif self._device.mode == HVACAction.COOLING:
            return HVACAction.COOLING
        else:
            return HVACAction.IDLE

    @property
    def hvac_modes(self) -> List[str]:
        return [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL]

    @property
    def preset_mode(self) -> Optional[str]:
        if self._device.mode is not None:
            return self._device.mode.name
        return None

    @property
    def preset_modes(self) -> List[str]:
        return [e.name for e in ThermostatV3Mode]

    @property
    def supported_features(self):
        return self._flags


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]  # type
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices()
        new_entities = []
        devs = filter(lambda d: isinstance(d, Mts100v3Valve), devices)

        for d in devs:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = ValveEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        async_add_entities(new_entities, True)

    coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    coordinator.async_add_listener(entity_adder_callback)
    # Run the entity adder a first time during setup
    entity_adder_callback()

# TODO: Implement entry unload
# TODO: Unload entry
# TODO: Remove entry


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

