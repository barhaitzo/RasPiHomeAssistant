# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Always-on Hebrew voice assistant running on Raspberry Pi 5 + Hailo-8L hat. Controls two AC units:
- Tadiran/Electra (living room) via `aioelectrasmart`
- Sensibo (bedroom) via direct REST calls to `home.sensibo.com/api/v2`

## Running locally (dev/test)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in credentials
python main.py        # runs with stdin input until mic is wired
```

## Architecture

```
voice/vad.py          → Silero VAD, always listening, triggers on speech
voice/transcriber.py  → faster-whisper, language=he
parser/command_parser.py → keyword matching → ParsedCommand
main.py dispatch()    → routes ParsedCommand to correct ACController
controllers/          → ElectraController, SensiboController (both async)
```

Device-to-controller mapping and room keywords live in `config.yaml`. Credentials in `.env`.

## Key design decisions

- `parse()` in `command_parser.py` is pure keyword/regex — no LLM, no network. Must stay sub-millisecond.
- `ACController.set_state()` always takes a full `ACState`. Use `current.with_changes(**kwargs)` to produce it; never construct ACState from scratch in dispatch code.
- Sensibo uses `httpx` directly (no extra library) — the API is simple enough.
- `load_config()` in the parser must be called before any `parse()` calls so room keywords match config.yaml.

## Adding a new device

1. Add entry to `config.yaml` under `devices:`
2. Implement `ACController` subclass in `controllers/`
3. Register it in `_build_controllers()` in `main.py`

## Hailo acceleration (phase 2)

The Hailo-8L will accelerate the Whisper encoder. Hailo Python bindings are installed system-wide; the venv is created with `--system-site-packages` to access them. The voice pipeline stubs in `voice/` are where this integration goes.
