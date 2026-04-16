from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class Mode(str, Enum):
    COOL = "cool"
    HEAT = "heat"
    FAN = "fan"
    AUTO = "auto"
    DRY = "dry"


class FanSpeed(str, Enum):
    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ACState:
    power: bool
    mode: Mode
    temperature: int
    fan_speed: FanSpeed

    def with_changes(self, **kwargs) -> "ACState":
        """Return a copy of this state with the given fields overridden."""
        data = {
            "power": self.power,
            "mode": self.mode,
            "temperature": self.temperature,
            "fan_speed": self.fan_speed,
        }
        data.update(kwargs)
        return ACState(**data)


class ACController(ABC):
    """Unified interface for all AC controllers."""

    @abstractmethod
    async def get_state(self) -> ACState:
        """Fetch the current AC state from the device/cloud."""
        ...

    @abstractmethod
    async def set_state(self, state: ACState) -> None:
        """Push a full AC state to the device."""
        ...

    async def turn_on(self) -> None:
        current = await self.get_state()
        await self.set_state(current.with_changes(power=True))

    async def turn_off(self) -> None:
        current = await self.get_state()
        await self.set_state(current.with_changes(power=False))

    async def set_temperature(self, temp: int) -> None:
        current = await self.get_state()
        await self.set_state(current.with_changes(temperature=temp))

    async def adjust_temperature(self, delta: int) -> None:
        current = await self.get_state()
        new_temp = max(16, min(30, current.temperature + delta))
        await self.set_state(current.with_changes(temperature=new_temp))

    async def set_mode(self, mode: Mode) -> None:
        current = await self.get_state()
        await self.set_state(current.with_changes(power=True, mode=mode))
