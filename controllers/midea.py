import os
from msmart.device import AirConditioner as MideaAC
from .base import ACController, ACState, Mode, FanSpeed


_MODE_TO_MIDEA = {
    Mode.COOL: MideaAC.OperationalMode.COOL,
    Mode.HEAT: MideaAC.OperationalMode.HEAT,
    Mode.FAN:  MideaAC.OperationalMode.FAN_ONLY,
    Mode.AUTO: MideaAC.OperationalMode.AUTO,
    Mode.DRY:  MideaAC.OperationalMode.DRY,
}
_MODE_FROM_MIDEA = {v: k for k, v in _MODE_TO_MIDEA.items()}

_FAN_TO_MIDEA = {
    FanSpeed.AUTO:   MideaAC.FanSpeed.AUTO,
    FanSpeed.LOW:    MideaAC.FanSpeed.LOW,
    FanSpeed.MEDIUM: MideaAC.FanSpeed.MEDIUM,
    FanSpeed.HIGH:   MideaAC.FanSpeed.HIGH,
}
_FAN_FROM_MIDEA = {v: k for k, v in _FAN_TO_MIDEA.items()}


class MideaController(ACController):
    """
    Controls a Midea-protocol AC (Tadiran/Electra via MSmartHome) over local LAN.

    Requires in config.yaml (under the device entry):
        ip:        "192.168.1.144"
        port:      6444
        device_id: 150633094414140

    Requires in .env:
        MIDEA_TOKEN  — from msmart-ng discovery (hex string)
        MIDEA_KEY    — from msmart-ng discovery (hex string)
    """

    def __init__(self, ip: str, device_id: int, port: int = 6444):
        self._ip = ip
        self._device_id = device_id
        self._port = port
        self._token = bytes.fromhex(os.environ["MIDEA_TOKEN"])
        self._key = bytes.fromhex(os.environ["MIDEA_KEY"])

    async def _get_device(self) -> MideaAC:
        device = MideaAC(ip=self._ip, device_id=self._device_id, port=self._port)
        await device.authenticate(self._token, self._key)
        return device

    async def get_state(self) -> ACState:
        device = await self._get_device()
        await device.refresh()
        return ACState(
            power=device.power_state,
            mode=_MODE_FROM_MIDEA.get(device.operational_mode, Mode.COOL),
            temperature=int(device.target_temperature),
            fan_speed=_FAN_FROM_MIDEA.get(device.fan_speed, FanSpeed.AUTO),
        )

    async def set_state(self, state: ACState) -> None:
        device = await self._get_device()
        await device.refresh()  # read current state before modifying
        device.power_state = state.power
        if state.power:
            device.operational_mode = _MODE_TO_MIDEA[state.mode]
            device.target_temperature = float(state.temperature)
            device.fan_speed = _FAN_TO_MIDEA[state.fan_speed]
        await device.apply()
