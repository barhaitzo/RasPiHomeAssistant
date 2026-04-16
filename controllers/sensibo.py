import os
import httpx
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


class SensiboController(ACController):
    def __init__(self, pod_uid: str | None = None, pod_name: str | None = None):
        """
        Provide either pod_uid (faster) or pod_name to auto-discover.
        Get pod UIDs from: GET https://home.sensibo.com/api/v2/users/me/pods
        """
        self._api_key = os.environ["SENSIBO_API_KEY"]
        self._pod_uid = pod_uid
        self._pod_name = pod_name

    def _params(self, **extra) -> dict:
        return {"apiKey": self._api_key, **extra}

    async def _ensure_uid(self) -> str:
        if self._pod_uid is None:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{_BASE}/users/me/pods",
                    params=self._params(fields="id,room"),
                )
                r.raise_for_status()
                pods = r.json()["result"]
                match = next(
                    (p for p in pods if p["room"]["name"] == self._pod_name),
                    None,
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
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{_BASE}/pods/{uid}/acStates",
                params=self._params(limit=1, fields="acState"),
            )
            r.raise_for_status()
        ac = r.json()["result"][0]["acState"]
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
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{_BASE}/pods/{uid}/acStates",
                params=self._params(),
                json=payload,
            )
            r.raise_for_status()
