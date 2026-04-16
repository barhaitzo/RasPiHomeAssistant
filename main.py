"""
pi_home_assistant — main event loop

Pipeline:
  Microphone → VAD → Whisper (Hebrew) → CommandParser → ACController → TTS
"""

import asyncio
import os
import sys

# Ensure Hebrew text prints correctly on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
import yaml
from dotenv import load_dotenv

from controllers.midea import MideaController
from controllers.sensibo import SensiboController
from controllers.base import ACController, Mode, FanSpeed
from parser.command_parser import Action, ParsedCommand, load_config
import parser.llm_parser as llm_parser

load_dotenv()

# ── load config ───────────────────────────────────────────────────────────────

with open("config.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

load_config(cfg["devices"], cfg["default_device"])

llm_cfg = cfg.get("llm_parser", {})
llm_parser.load_config(
    cfg["devices"],
    cfg["default_device"],
    model=llm_cfg.get("model", "qwen2.5:1.5b"),
)

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
    return await _dispatch_inner(command, ctrl)


async def _dispatch_inner(command: ParsedCommand, ctrl) -> str:
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


# ── voice dispatch wrapper ────────────────────────────────────────────────────

async def _voice_dispatch(text: str) -> str:
    """Parse raw transcribed text and dispatch to the right controller."""
    command = await asyncio.get_running_loop().run_in_executor(
        None, llm_parser.parse, text
    )
    print(f"  parsed → {command}")
    return await dispatch(command)


# ── main loop ─────────────────────────────────────────────────────────────────

async def main():
    stdin_mode = "--stdin" in sys.argv

    if stdin_mode:
        # Text-input testing mode (no mic / Whisper needed)
        print("pi_home_assistant מוכן — מצב stdin (בדיקות)\n")
        while True:
            try:
                text = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: input("פקודה: ")
                )
            except (EOFError, KeyboardInterrupt):
                print("\nיוצא")
                break

            command = await asyncio.get_running_loop().run_in_executor(
                None, llm_parser.parse, text
            )
            print(f"  parsed → {command}")
            result = await dispatch(command)
            print(f"  → {result}\n")
    else:
        # Full voice pipeline — import here so --stdin mode skips faster-whisper entirely
        from voice.transcriber import Transcriber
        from voice.pipeline import VoicePipeline

        voice_cfg = cfg.get("voice", {})
        model_name = voice_cfg.get("model", "openai/whisper-large-v3")
        vad_threshold = float(voice_cfg.get("vad_threshold", 0.02))

        wake_words_cfg = voice_cfg.get("wake_word", [])
        if isinstance(wake_words_cfg, str):
            wake_words_cfg = [wake_words_cfg]

        transcriber = Transcriber(model_name=model_name)
        pipeline = VoicePipeline(
            transcriber=transcriber,
            dispatch=_voice_dispatch,
            energy_threshold=vad_threshold,
            wake_words=wake_words_cfg or None,
        )
        await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())
