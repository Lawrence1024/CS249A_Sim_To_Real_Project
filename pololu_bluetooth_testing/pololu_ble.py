# pololu_ble.py - BLE module for Pololu robot control
# (macOS + Bleak ≥ 1.0)
import asyncio
from typing import Optional, Union
from bleak import BleakScanner, BleakClient, BLEDevice

import struct

SERVICE_UUID = "FFE0"
CHAR_UUID = "FFE1"

TARGET_NAMES = {"HMSoft", "HM-10", "DSD TECH"}


class PololuBLE:
    """BLE client for Pololu robot control via HM-10 module."""
    
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.device: Optional[BLEDevice] = None
        self._connected = False
    
    async def find_device(self, timeout: float = 5.0) -> Optional[BLEDevice]:
        """Scan and find HM-10 device.
        
        Args:
            timeout: Scan timeout in seconds
            
        Returns:
            BleakDevice if found, None otherwise
        """
        print("Scanning for HM-10...")
        devices = await BleakScanner.discover(timeout=timeout)
        for d in devices:
            if (d.name and d.name in TARGET_NAMES) or ("HM" in (d.name or "")):
                return d
        return None
    
    async def connect(self, device: Optional[BLEDevice] = None, timeout: float = 5.0) -> bool:
        """Connect to HM-10 device.
        
        Args:
            device: Optional BLEDevice. If None, will scan for device.
            timeout: Scan timeout if device is None
            
        Returns:
            True if connected successfully, False otherwise
        """
        if self._connected and self.client and self.client.is_connected:
            print("Already connected")
            return True
        
        if device is None:
            device = await self.find_device(timeout)
        
        if not device:
            print("No HM-10-like device found. Move closer or verify with a BLE scanner.")
            return False
        
        try:
            self.device = device
            self.client = BleakClient(device)
            await self.client.connect()
            self._connected = True
            
            # Subscribe to notifications (optional)
            await self.client.start_notify(CHAR_UUID, lambda c, d: None)
            print(f"Connected to: {device}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self._connected = False
            self.client = None
            return False
    
    async def disconnect(self):
        """Disconnect from the device."""
        if self.client and self._connected:
            try:
                await self.client.disconnect()
            except Exception as e:
                print(f"Disconnect error: {e}")
            finally:
                self._connected = False
                self.client = None
                self.device = None
    
    async def send_command(self, command: Union[bytes, str]) -> bool:
        """Send command to Pololu via BLE.
        
        Args:
            command: Command to send (bytes or string)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self._connected or not self.client or not self.client.is_connected:
            print("Not connected. Please connect first.")
            return False
        
        try:
            # Convert string to bytes if needed
            if isinstance(command, str):
                cmd_bytes = command.encode('utf-8')
            else:
                cmd_bytes = command
            
            await self.client.write_gatt_char(CHAR_UUID, cmd_bytes, response=False)
            #print(f"Sent: {cmd_bytes}")
            return True
        except Exception as e:
            print(f"Send command failed: {e}")
            return False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected and self.client and self.client.is_connectedble_sender

    async def send_wheel_speed_command(self, left_rads: float, right_rads: float):
        # Use 'A' as the header character byte
        command_char = b'A' 
        # '<cff' packs 1-byte char, 4-byte float, 4-byte float (Total 9 bytes)
        command_bytes = struct.pack('<cff', command_char, left_rads, right_rads)
        
        # You would then call your BLE send function: 
        await self.send_command(command_bytes)








# Example usage
if __name__ == "__main__":
    async def main():
        # Example 1: Using the class directly
        async with PololuBLE() as pololu:
            await pololu.send_command(b"F")
            await pololu.send_command("B")
            await pololu.send_command(b"Stop\x00")
        
        # Example 2: Using convenience function
        send_ble_command("S")
        send_ble_command(b"Forward\x00")
    
    asyncio.run(main())

