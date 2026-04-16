"""
LLM-based Hebrew command parser using a local Ollama model.

Replaces the keyword parser with a small language model that understands
natural Hebrew phrasing and maps it to the same ParsedCommand struct.

Requires Ollama running locally:
  https://ollama.com  →  ollama pull qwen2.5:1.5b
"""

import json
import requests
from .command_parser import ParsedCommand, Action, parse as keyword_parse

OLLAMA_URL = "http://localhost:11434/api/generate"

_SYSTEM_TEMPLATE = """\
You are a parser for a Hebrew smart home voice assistant.
Convert the Hebrew command into a JSON object. Respond with JSON only — no explanation.

Available devices:
{devices}

Available actions:
- POWER_ON   — turn the AC on
- POWER_OFF  — turn the AC off
- SET_TEMP   — set an exact temperature; value = integer (Celsius, 16–30)
- DELTA_TEMP — raise or lower temperature by one degree; value = 1 or -1
- SET_MODE   — change operating mode; value = one of: cool, heat, fan, auto, dry
- SET_FAN    — change fan speed; value = one of: auto, low, medium, high
- UNKNOWN    — cannot understand the command

Default device when none is mentioned: "{default_device}"

Output format (strict JSON, nothing else):
{{"device": "<device_key>", "action": "<ACTION>", "value": <null | integer | string>}}\
"""

_system_prompt: str = ""
_default_device: str = "living_room"
_model: str = "qwen2.5:1.5b"


def load_config(devices: dict, default_device: str, model: str = "qwen2.5:1.5b") -> None:
    """Call once at startup with the devices block from config.yaml."""
    global _system_prompt, _default_device, _model
    _model = model
    _default_device = default_device
    lines = []
    for key, cfg in devices.items():
        keywords = ", ".join(cfg.get("keywords_he", []))
        lines.append(f'- "{key}" ({cfg.get("display_name", key)}): {keywords}')
    _system_prompt = _SYSTEM_TEMPLATE.format(
        devices="\n".join(lines),
        default_device=default_device,
    )
    _check_ollama()


def _check_ollama() -> None:
    try:
        r = requests.get("http://localhost:11434", timeout=2.0)
        print(f"  [llm_parser] Ollama running — model: {_model}")
    except Exception:
        print(f"  [llm_parser] Ollama not found — falling back to keyword parser")


def parse(text: str) -> ParsedCommand:
    """
    Parse a Hebrew command via the local Ollama model.
    Falls back to the keyword parser if Ollama is unreachable or returns garbage.
    """
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": _model,
                "system": _system_prompt,
                "prompt": text,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},  # deterministic
            },
            timeout=15.0,
        )
        r.raise_for_status()
        result = json.loads(r.json()["response"])

        device = result.get("device", _default_device)
        action = Action[result.get("action", "UNKNOWN")]
        value = result.get("value")
        if isinstance(value, float):
            value = int(value)

        return ParsedCommand(action=action, device_key=device, value=value)

    except Exception as e:
        print(f"  [llm_parser] fallback to keywords ({e})")
        return keyword_parse(text)
