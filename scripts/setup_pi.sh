#!/bin/bash
# Pi 5 setup for pi_home_assistant
# Run once after cloning the repo onto the Pi.
# Assumes: Raspberry Pi OS Bookworm (64-bit), Python 3.11+, Hailo drivers already installed.

set -e

echo "==> Updating system packages"
sudo apt-get update -qq
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    portaudio19-dev \   # required by sounddevice
    libsndfile1         # required by sounddevice

echo "==> Creating virtual environment"
python3 -m venv .venv --system-site-packages
# --system-site-packages lets the venv access the Hailo Python bindings
# which are installed system-wide by the Hailo SDK

source .venv/bin/activate

echo "==> Installing Python dependencies"
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Downloading Whisper model (this will take a few minutes)"
# faster-whisper downloads on first use, but we pre-fetch to avoid delay at runtime
python3 - <<'EOF'
from faster_whisper import WhisperModel
print("Downloading ivrit-ai/whisper-large-v2-tuned ...")
WhisperModel("ivrit-ai/whisper-large-v2-tuned", device="cpu", compute_type="int8")
print("Done.")
EOF

echo "==> Copying env file"
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  !! Edit .env and fill in your credentials before running main.py"
fi

echo ""
echo "Setup complete. To run:"
echo "  source .venv/bin/activate"
echo "  python main.py"
