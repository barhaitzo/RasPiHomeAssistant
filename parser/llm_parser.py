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
{{"device": "<device_key>", "action": "<ACTION>", "value": <null | integer | string>}}

Examples:
{examples}\
"""

# Few-shot examples injected dynamically with the actual device keys
_EXAMPLES_TEMPLATE = """\
Input: תכבה את המזגן בחדר שינה
Output: {{"device": "bedroom", "action": "POWER_OFF", "value": null}}

Input: תדליק את המזגן בסלון
Output: {{"device": "living_room", "action": "POWER_ON", "value": null}}

Input: תעלה טמפרטורה ל-24
Output: {{"device": "{default_device}", "action": "SET_TEMP", "value": 24}}

Input: קצת יותר חם בחדר
Output: {{"device": "bedroom", "action": "DELTA_TEMP", "value": 1}}

Input: תוריד את הטמפרטורה בסלון
Output: {{"device": "living_room", "action": "DELTA_TEMP", "value": -1}}

Input: עבור למצב קירור
Output: {{"device": "{default_device}", "action": "SET_MODE", "value": "cool"}}

Input: כבה את המזגן בבית
Output: {{"device": "{default_device}", "action": "POWER_OFF", "value": null}}

Input: תגדיר את הטמפרטורה בחדר שינה על 22
Output: {{"device": "bedroom", "action": "SET_TEMP", "value": 22}}\
"""

_VALID_ACTIONS = {a.name for a in Action}
_system_prompt: str = ""
_default_device: str = "living_room"
_valid_devices: set[str] = set()
_model: str = "qwen2.5:1.5b"


def load_config(devices: dict, default_device: str, model: str = "qwen2.5:1.5b") -> None:
    """Call once at startup with the devices block from config.yaml."""
    global _system_prompt, _default_device, _valid_devices, _model
    _model = model
    _default_device = default_device
    _valid_devices = set(devices.keys())

    lines = []
    for key, cfg in devices.items():
        keywords = ", ".join(cfg.get("keywords_he", []))
        lines.append(f'- "{key}" ({cfg.get("display_name", key)}): {keywords}')

    examples = _EXAMPLES_TEMPLATE.format(default_device=default_device)

    _system_prompt = _SYSTEM_TEMPLATE.format(
        devices="\n".join(lines),
        default_device=default_device,
        examples=examples,
    )
    _check_ollama()


def _check_ollama() -> None:
    try:
        requests.get("http://localhost:11434", timeout=2.0)
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
                "prompt": f"Input: {text}\nOutput:",
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
            timeout=15.0,
        )
        r.raise_for_status()
        result = json.loads(r.json()["response"])

        device = result.get("device", _default_device)
        action_str = result.get("action", "UNKNOWN")
        value = result.get("value")

        # Validate — fall back to keywords if model returned garbage
        if device not in _valid_devices:
            raise ValueError(f"unknown device: {device!r}")
        if action_str not in _VALID_ACTIONS:
            raise ValueError(f"unknown action: {action_str!r}")

        if isinstance(value, float):
            value = int(value)

        return ParsedCommand(action=Action[action_str], device_key=device, value=value)

    except Exception as e:
        print(f"  [llm_parser] fallback to keywords ({e})")
        return keyword_parse(text)
