"""
Connectivity test for Sensibo — run from project root:
  python scripts/test_sensibo.py

Prints current AC state. No changes are made to the device.
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
from controllers.sensibo import SensiboController

load_dotenv()

async def main():
    ctrl = SensiboController(pod_uid="4FJoTnQo")

    print("Reading state...")
    state = await ctrl.get_state()
    print(f"  Power  : {'ON' if state.power else 'OFF'}")
    print(f"  Mode   : {state.mode.value}")
    print(f"  Temp   : {state.temperature}°C")
    print(f"  Fan    : {state.fan_speed.value}")

asyncio.run(main())
