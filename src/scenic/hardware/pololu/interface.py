"""Hardware interface for Pololu robot control.

This module provides a simple interface to control Pololu robots via BLE
and receive position/orientation feedback from motion capture.
"""

import asyncio
import sys
import os

# Add paths for mocap and BLE modules
# Go up from hardware/pololu to Scenic root: ../../../../ (4 levels)
_scenic_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../'))
if _scenic_root not in sys.path:
    sys.path.insert(0, _scenic_root)

from mocap.mocap_estimator import MocapEstimator, Pose
from pololu_bluetooth_testing.pololu_ble import PololuBLE

class HardwareInterface:
    """Hardware interface for Pololu robot with BLE control and mocap feedback.
    
    This class wraps the BLE and mocap interfaces to provide a unified
    interface for controlling physical Pololu robots from Scenic scenarios.
    """
    
    def __init__(self, mocap_target_id=15):
        """Initialize hardware interface.
        
        Args:
            mocap_target_id: Motion capture target ID for this robot
        """
        self.mocap_estimator = MocapEstimator(target_id=mocap_target_id)
        self.ble_sender = PololuBLE()
        self._connected = False
    
    async def connect(self):
        """Connect to BLE device.
        
        Returns:
            True if connected successfully, False otherwise
        """
        if await self.ble_sender.connect():
            self._connected = True
            return True
        return False
    
    async def send_wheel_speed_command(self, left_speed: float, right_speed: float):
        """Send wheel speed command to robot via BLE (async version).
        
        This method directly uses the async BLE interface, avoiding issues
        with nested event loops.
        
        Args:
            left_speed: Speed for left wheel (-255 to 255)
            right_speed: Speed for right wheel (-255 to 255)
        """
        if not self._connected:
            raise RuntimeError("BLE not connected. Call connect() first.")
        
        # Clamp speeds to valid range
        left_speed = max(-255, min(255, int(left_speed)))
        right_speed = max(-255, min(255, int(right_speed)))
        
        # Create command bytes
        command = bytes([left_speed & 0xFF, right_speed & 0xFF])
        
        # Send command via async interface
        await self.ble_sender.send_command(command)
    
    def get_pose(self) -> Pose:
        """Get current pose from motion capture system.
        
        Returns:
            Pose object with position (x, y, z) and orientation (qx, qy, qz, qw)
        """
        return self.mocap_estimator.get_pose()
    
    async def disconnect(self):
        """Disconnect from BLE device."""
        if self._connected:
            await self.ble_sender.disconnect()
            self._connected = False
    
    def is_connected(self) -> bool:
        """Check if BLE is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self._connected

