"""
Discover Switcher devices on the local network.
Run from project root:
  python scripts/discover_switcher.py

Press Ctrl+C after your device appears (usually within 30 seconds —
the device broadcasts a UDP packet every ~4 seconds).
"""

import asyncio
from aioswitcher.bridge import SwitcherBridge

seen = {}

async def on_device(device):
    if device.device_id not in seen:
        seen[device.device_id] = device
        print(f"\nFound device:")
        print(f"  Name       : {device.name}")
        print(f"  Type       : {device.device_type.name}")
        print(f"  IP         : {device.ip_address}")
        print(f"  Device ID  : {device.device_id}   ← add to .env as SWITCHER_DEVICE_ID")
        print(f"  Device Key : {device.device_key}  ← add to .env as SWITCHER_DEVICE_KEY")
        print(f"  State      : {device.device_state.name}")
        if hasattr(device, 'remaining_time') and device.remaining_time:
            print(f"  Remaining  : {device.remaining_time}")

async def main():
    print("Listening for Switcher broadcasts (Ctrl+C to stop)...")
    async with SwitcherBridge(on_device):
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nDone.")
