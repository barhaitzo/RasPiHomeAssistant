import asyncio
import os
import requests
from .base import ACController, ACState, Mode, FanSpeed

_BASE = "https://home.sensibo.com/api/v2"

_MODE_MAP = {
    "cool": Mode.COOL,
    "heat": Mode.HEAT,
    "fan": Mode.FAN,
    "auto": Mode.AUTO,
    "dry": Mode.DRY,
}
_MODE_MAP_REV = {v: k for k, v in _MODE_MAP.items()}

_FAN_MAP = {
    "auto": FanSpeed.AUTO,
    "low": FanSpeed.LOW,
    "medium": FanSpeed.MEDIUM,
    "medium_high": FanSpeed.HIGH,
    "high": FanSpeed.HIGH,
    "strong": FanSpeed.HIGH,
}
_FAN_MAP_REV = {
    FanSpeed.AUTO: "auto",
    FanSpeed.LOW: "low",
    FanSpeed.MEDIUM: "medium",
    FanSpeed.HIGH: "high",
}


def _get(path: str, api_key: str, **params) -> dict:
    r = requests.get(
        f"{_BASE}{path}",
        params={"apiKey": api_key, **params},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def _post(path: str, api_key: str, payload: dict) -> dict:
    r = requests.post(
        f"{_BASE}{path}",
        params={"apiKey": api_key},
        json=payload,
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


class SensiboController(ACController):
    def __init__(self, pod_uid: str | None = None, pod_name: str | None = None):
        self._api_key = os.environ["SENSIBO_API_KEY"]
        self._pod_uid = pod_uid
        self._pod_name = pod_name

    async def _ensure_uid(self) -> str:
        if self._pod_uid is None:
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(
                None, lambda: _get("/users/me/pods", self._api_key, fields="id,room")
            )
            pods = data["result"]
            match = next(
                (p for p in pods if p["room"]["name"] == self._pod_name), None
            )
            if match is None:
                available = [p["room"]["name"] for p in pods]
                raise ValueError(
                    f"Pod '{self._pod_name}' not found. Available: {available}"
                )
            self._pod_uid = match["id"]
        return self._pod_uid

    async def get_state(self) -> ACState:
        uid = await self._ensure_uid()
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(
            None, lambda: _get(f"/pods/{uid}/acStates", self._api_key, limit=1, fields="acState")
        )
        ac = data["result"][0]["acState"]
        return ACState(
            power=ac["on"],
            mode=_MODE_MAP.get(ac.get("mode", "cool"), Mode.COOL),
            temperature=int(ac.get("targetTemperature", 24)),
            fan_speed=_FAN_MAP.get(ac.get("fanLevel", "auto"), FanSpeed.AUTO),
        )

    async def set_state(self, state: ACState) -> None:
        uid = await self._ensure_uid()
        payload = {
            "acState": {
                "on": state.power,
                "mode": _MODE_MAP_REV[state.mode],
                "targetTemperature": state.temperature,
                "fanLevel": _FAN_MAP_REV[state.fan_speed],
                "temperatureUnit": "C",
            }
        }
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, lambda: _post(f"/pods/{uid}/acStates", self._api_key, payload)
        )
