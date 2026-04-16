"""
Hebrew voice command parser.

Converts a raw transcribed Hebrew string into a structured ParsedCommand
that the main loop can dispatch to the right AC controller.

Design: pure keyword/regex matching — no LLM, no network, sub-millisecond.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class Action(Enum):
    POWER_ON = auto()
    POWER_OFF = auto()
    SET_TEMP = auto()       # absolute: "תגדיר על 22"
    DELTA_TEMP = auto()     # relative: "יותר קר", "תעלה"
    SET_MODE = auto()
    SET_FAN = auto()
    UNKNOWN = auto()


@dataclass
class ParsedCommand:
    action: Action
    device_key: str             # matches a key in config.yaml devices
    value: Any = None           # int for temp, str for mode/fan, int (+1/-1) for delta


# ── room / device keywords ────────────────────────────────────────────────────
# Loaded dynamically from config at startup via `load_config()`; these are
# fallback defaults that mirror config.yaml.
_DEVICE_KEYWORDS: dict[str, list[str]] = {
    "living_room": ["סלון", "הסלון"],
    "bedroom": ["שינה", "חדר שינה", "חדר"],
}
_DEFAULT_DEVICE = "living_room"

# ── intent keyword lists ──────────────────────────────────────────────────────

_POWER_ON = ["הדלק", "תדליק", "פתח", "תפתח", "הפעל", "תפעיל", "on"]
_POWER_OFF = ["כבה", "תכבה", "סגור", "תסגור", "עצור", "תעצור", "off"]

_MODE_KEYWORDS = {
    "cool": ["קירור", "קר", "תקרר", "מצב קירור", "cool"],
    "heat": ["חימום", "חם", "תחמם", "מצב חימום", "heat"],
    "fan":  ["מאוורר", "מאורר", "אוויר", "fan"],
    "auto": ["אוטומטי", "אוטו", "auto"],
    "dry":  ["יבש", "מייבש", "dry"],
}

_FAN_KEYWORDS = {
    "auto":   ["מאוורר אוטומטי", "מהירות אוטומטית"],
    "low":    ["מהירות נמוכה", "חלש", "חלשה"],
    "medium": ["מהירות בינונית", "בינוני"],
    "high":   ["מהירות גבוהה", "חזק", "חזקה"],
}

# "more cold" in Hebrew = lower temp; "more hot" = raise temp
_TEMP_DOWN = ["יותר קר", "הוריד", "תוריד", "הנמך", "תנמיך", "פחות חם"]
_TEMP_UP   = ["יותר חם", "העלה", "תעלה", "הגדל", "תגדיל", "פחות קר"]

# Hebrew words for numbers 16-30 (the realistic AC temp range)
_HE_NUMBERS = {
    "שש עשרה": 16, "שבע עשרה": 17, "שמונה עשרה": 18, "תשע עשרה": 19,
    "עשרים": 20,
    "עשרים ואחת": 21, "עשרים ואחד": 21,
    "עשרים ושתיים": 22, "עשרים ושניים": 22,
    "עשרים ושלוש": 23, "עשרים ושלושה": 23,
    "עשרים וארבע": 24, "עשרים וארבעה": 24,
    "עשרים וחמש": 25, "עשרים וחמישה": 25,
    "עשרים ושש": 26, "עשרים ושישה": 26,
    "עשרים ושבע": 27, "עשרים ושבעה": 27,
    "עשרים ושמונה": 28,
    "עשרים ותשע": 29, "עשרים ותשעה": 29,
    "שלושים": 30,
}


def load_config(devices: dict, default_device: str) -> None:
    """
    Call once at startup with the devices block from config.yaml so the parser
    uses the same room keywords as the rest of the system.

    devices = {
        "living_room": {"keywords_he": ["סלון", ...], ...},
        ...
    }
    """
    global _DEVICE_KEYWORDS, _DEFAULT_DEVICE
    _DEVICE_KEYWORDS = {
        key: cfg["keywords_he"] for key, cfg in devices.items()
    }
    _DEFAULT_DEVICE = default_device


# ── internal helpers ──────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase, strip extra whitespace, remove punctuation."""
    text = text.strip().lower()
    text = re.sub(r"[.,!?\"']", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_device(text: str) -> str:
    """Return the device key for the first room keyword found, else default."""
    for device_key, keywords in _DEVICE_KEYWORDS.items():
        for kw in sorted(keywords, key=len, reverse=True):  # longest match first
            if kw.lower() in text:
                return device_key
    return _DEFAULT_DEVICE


def _extract_temperature(text: str) -> int | None:
    """Extract an explicit temperature value (Arabic digits or Hebrew words)."""
    # Arabic digits: "22", "22 מעלות", "על 22"
    match = re.search(r"\b(1[6-9]|2[0-9]|30)\b", text)
    if match:
        return int(match.group(1))

    # Hebrew words
    for he_word, value in sorted(_HE_NUMBERS.items(), key=lambda x: -len(x[0])):
        if he_word in text:
            return value

    return None


def _any_keyword(text: str, keywords: list[str]) -> bool:
    return any(kw.lower() in text for kw in keywords)


# ── public API ────────────────────────────────────────────────────────────────

def parse(text: str) -> ParsedCommand:
    """
    Parse a Hebrew voice command string into a ParsedCommand.

    >>> parse("תדליק את המזגן בסלון")
    ParsedCommand(action=<Action.POWER_ON: 1>, device_key='living_room', value=None)

    >>> parse("תוריד את הטמפרטורה ל-22 בחדר שינה")
    ParsedCommand(action=<Action.SET_TEMP: 3>, device_key='bedroom', value=22)
    """
    normalized = _normalize(text)
    device_key = _extract_device(normalized)

    # Power off (check before power on — "כבה" is unambiguous)
    if _any_keyword(normalized, _POWER_OFF):
        return ParsedCommand(Action.POWER_OFF, device_key)

    # Power on
    if _any_keyword(normalized, _POWER_ON):
        return ParsedCommand(Action.POWER_ON, device_key)

    # Mode change
    for mode, keywords in _MODE_KEYWORDS.items():
        if _any_keyword(normalized, keywords):
            return ParsedCommand(Action.SET_MODE, device_key, value=mode)

    # Fan speed
    for fan_speed, keywords in _FAN_KEYWORDS.items():
        if _any_keyword(normalized, keywords):
            return ParsedCommand(Action.SET_FAN, device_key, value=fan_speed)

    # Explicit temperature ("הגדר על 22", "22 מעלות")
    temp = _extract_temperature(normalized)
    if temp is not None:
        return ParsedCommand(Action.SET_TEMP, device_key, value=temp)

    # Relative temperature ("יותר קר", "תעלה")
    if _any_keyword(normalized, _TEMP_DOWN):
        return ParsedCommand(Action.DELTA_TEMP, device_key, value=-1)
    if _any_keyword(normalized, _TEMP_UP):
        return ParsedCommand(Action.DELTA_TEMP, device_key, value=+1)

    return ParsedCommand(Action.UNKNOWN, device_key)
