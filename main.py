"""
pi_home_assistant — main event loop

Pipeline:
  Microphone → VAD → Whisper (Hebrew) → CommandParser → ACController
"""

import asyncio
import os
import yaml
from dotenv import load_dotenv

from controllers.midea import MideaController
from controllers.sensibo import SensiboController
from controllers.base import ACController, Mode, FanSpeed
from parser.command_parser import Action, ParsedCommand, parse, load_config

load_dotenv()

# ── load config ───────────────────────────────────────────────────────────────

with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

load_config(cfg["devices"], cfg["default_device"])

# ── build controller registry ─────────────────────────────────────────────────

def _build_controllers() -> dict[str, ACController]:
    controllers: dict[str, ACController] = {}
    for key, device_cfg in cfg["devices"].items():
        kind = device_cfg["controller"]
        if kind == "midea":
            controllers[key] = MideaController(
                ip=device_cfg["ip"],
                device_id=device_cfg["device_id"],
                port=device_cfg.get("port", 6444),
            )
        elif kind == "sensibo":
            controllers[key] = SensiboController(
                pod_uid=device_cfg.get("pod_uid"),
                pod_name=device_cfg.get("display_name"),
            )
        else:
            raise ValueError(f"Unknown controller type: {kind}")
    return controllers


controllers = _build_controllers()


# ── command dispatcher ────────────────────────────────────────────────────────

async def dispatch(command: ParsedCommand) -> str:
    """Execute a parsed command and return a short Hebrew confirmation string."""
    ctrl = controllers.get(command.device_key)
    if ctrl is None:
        return f"המכשיר '{command.device_key}' לא נמצא"

    match command.action:
        case Action.POWER_ON:
            await ctrl.turn_on()
            return "הדלקתי את המזגן"
        case Action.POWER_OFF:
            await ctrl.turn_off()
            return "כיביתי את המזגן"
        case Action.SET_TEMP:
            await ctrl.set_temperature(command.value)
            return f"הגדרתי טמפרטורה ל-{command.value}"
        case Action.DELTA_TEMP:
            await ctrl.adjust_temperature(command.value)
            direction = "הורדתי" if command.value < 0 else "העלתי"
            return f"{direction} טמפרטורה ב-1 מעלה"
        case Action.SET_MODE:
            await ctrl.set_mode(Mode(command.value))
            return f"עברתי למצב {command.value}"
        case Action.SET_FAN:
            state = await ctrl.get_state()
            await ctrl.set_state(state.with_changes(fan_speed=FanSpeed(command.value)))
            return f"שיניתי מהירות מאוורר ל-{command.value}"
        case Action.UNKNOWN:
            return "לא הבנתי את הפקודה"


# ── main loop ─────────────────────────────────────────────────────────────────

async def main():
    print("pi_home_assistant מוכן — ממתין לפקודות קוליות")
    print("(voice pipeline not yet connected — testing via stdin)\n")

    # Temporary: read commands from stdin for testing before mic is wired up
    while True:
        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("פקודה: ")
            )
        except (EOFError, KeyboardInterrupt):
            print("\nיוצא")
            break

        command = parse(text)
        print(f"  parsed → {command}")
        result = await dispatch(command)
        print(f"  → {result}\n")


if __name__ == "__main__":
    asyncio.run(main())
