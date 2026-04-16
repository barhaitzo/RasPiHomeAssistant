"""
Connectivity test for the Midea LAN controller — run from project root:
  python scripts/test_midea.py

Reads current AC state. No changes made unless you uncomment the write test.
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
from controllers.midea import MideaController

load_dotenv()

async def main():
    ctrl = MideaController(ip="192.168.1.144", device_id=150633094414140, port=6444)

    print("Reading state...")
    state = await ctrl.get_state()
    print(f"  Power  : {'ON' if state.power else 'OFF'}")
    print(f"  Mode   : {state.mode.value}")
    print(f"  Temp   : {state.temperature}°C")
    print(f"  Fan    : {state.fan_speed.value}")

    # Uncomment to test a write (sets temp to current value — safe no-op):
    # print("\nWriting state back (no-op)...")
    # await ctrl.set_state(state)
    # print("  Done")

asyncio.run(main())
