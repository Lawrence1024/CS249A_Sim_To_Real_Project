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
#from mocap.mocap_dummy_estimator import MocapDummyEstimator as MocapEstimator, Pose
#from pololu_bluetooth_testing.pololu_ble_dummy import PololuBLEDummy as PololuBLE

# Dummy mocap classes commented out - using real mocap system
# class Pose:
#     """Very simple pose object for testing.
# 
#     Attributes:
#         x, y, z: position in meters
#         yaw: heading angle in radians
#     """
#     def __init__(self, x=0.0, y=0.0, z=0.0, yaw=0.0):
#         self.x = x
#         self.y = y
#         self.z = z
#         self._yaw = yaw
# 
#     def get_euler_zyx(self, degrees=False):
#         """Return (yaw, pitch, roll) in the format expected by the model.
# 
#         Your HardwarePololuRobot only uses the first component (yaw).
#         """
#         if degrees:
#             # radians → degrees
#             from math import degrees as rad2deg
#             return (rad2deg(self._yaw), 0.0, 0.0)
#         else:
#             return (self._yaw, 0.0, 0.0)
# 
# 
# class MocapEstimator:
#     """Dummy mocap estimator which never talks to the network.
# 
#     It just returns a fixed Pose, or you can update the pose manually.
#     For testing, it can simulate movement to prove mocap values are being read.
#     """
#     def __init__(self, target_id=None, *args, **kwargs):
#         self.target_id = target_id
#         # For testing: start with a DIFFERENT pose to prove mocap is being read
#         # This will show up in the behavior prints if mocap values are being used
#         self.pose = Pose(5.0, 10.0, 0.0, yaw=1.57)  # Different from robot start position!
#         # For testing: simulate movement to prove mocap is being read
#         self._call_count = 0
#         self._simulate_movement = True  # Set to False to disable movement simulation
# 
#     def get_pose(self) -> Pose:
#         """Return the current dummy pose.
#         
#         For testing: if _simulate_movement is True, this will gradually
#         change the pose to simulate the robot moving, proving that mocap
#         values are being read and used.
#         """
#         if self._simulate_movement:
#             # Simulate robot moving forward (0.01m per call for realistic speed)
#             # This will prove that mocap values are being read and used
#             # Move forward in the direction of current heading
#             import math
#             speed = 0.01  # meters per call (realistic speed)
#             current_yaw = self.pose._yaw
#             dx = speed * math.cos(current_yaw)
#             dy = speed * math.sin(current_yaw)
#             # Create new Pose with updated position
#             self.pose = Pose(
#                 self.pose.x + dx,
#                 self.pose.y + dy,
#                 self.pose.z,
#                 yaw=self.pose._yaw
#             )
#         
#         return self.pose
# 
#     # optional helpers if you want to move the robot manually in tests
#     def set_pose(self, x, y, z=0.0, yaw=0.0):
#         """Set the pose manually. This will override any simulated movement."""
#         self.pose = Pose(x, y, z, yaw)
#         self._call_count = 0  # Reset counter
#     
#     def set_simulate_movement(self, enable: bool):
#         """Enable/disable movement simulation for testing."""
#         self._simulate_movement = enable

class HardwareInterface:
    """Hardware interface for Pololu robot with BLE control and mocap feedback.
    
    This class wraps the BLE and mocap interfaces to provide a unified
    interface for controlling physical Pololu robots from Scenic scenarios.
    """
    
    def __init__(self, mocap_target_id=15, max_angular_velocity=10.0):
        """Initialize hardware interface.
        
        Args:
            mocap_target_id: Motion capture target ID for this robot
            max_angular_velocity: Maximum angular velocity in rad/s (default 10.0 to match Webots)
                                  This should match your hardware's max motor velocity
        """
        self.mocap_estimator = MocapEstimator(target_id=mocap_target_id)  # Real mocap system
        # self.mocap_estimator = MocapEstimator()  # Dummy mocap for testing (commented out)
        self.ble_sender = PololuBLE()
        self._connected = False
        self.max_angular_velocity = max_angular_velocity
        self._event_loop = None  # Will be set by run_pololu_hardware.py
    
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
        
        Converts Scenic motor speeds (0-100 range) to angular velocity (rad/s)
        using the same conversion as Webots, so hardware matches simulation.
        
        Args:
            left_speed: Motor speed from Scenic behavior (0-100 range)
            right_speed: Motor speed from Scenic behavior (0-100 range)
        """
        # Convert Scenic values (0-100) to angular velocity (rad/s) - same as Webots
        # Formula: angular_velocity = (scenic_speed / 100.0) * max_angular_velocity
        left_angular_vel = (left_speed / 100.0) * self.max_angular_velocity
        right_angular_vel = (right_speed / 100.0) * self.max_angular_velocity
        
        # convert to deg/s
        left_angular_vel = left_angular_vel * (180.0 / 3.141592653589793)
        right_angular_vel = right_angular_vel * (180.0 / 3.141592653589793)

        # The BLE command expects angular velocity values
        # Convert to the format expected by the hardware (check pololu_ble.py for format)
        # Based on pololu_ble.py line 149-153, it uses struct.pack('<cff', ...) for rad/s
        import struct
        command_char = b'A'  # Header character
        command_bytes = struct.pack('<cff', command_char, left_angular_vel, right_angular_vel)
        
        # Send command via async interface
        if self._connected:
            await self.ble_sender.send_command(command_bytes)
        # else:
        #     print(f"[BLE] Not connected: left={left_angular_vel:.3f} rad/s, right={right_angular_vel:.3f} rad/s")
    
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
    
    def send_wheel_speed_command_sync(self, left_speed: float, right_speed: float):
        """Synchronous wrapper for send_wheel_speed_command.
        
        Uses the stored event loop to run the async command synchronously.
        This is called from the simulation loop which is not async.
        
        Args:
            left_speed: Motor speed from Scenic behavior (0-100 range)
            right_speed: Motor speed from Scenic behavior (0-100 range)
        """
        loop = self._event_loop
        if loop is None:
            # Fallback: try to get current loop
            try:
                loop = asyncio.get_running_loop()
                # If loop is running, schedule as task (fire and forget)
                asyncio.create_task(
                    self.send_wheel_speed_command(left_speed, right_speed)
                )
                return
            except RuntimeError:
                # No loop running, create temporary one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        self.send_wheel_speed_command(left_speed, right_speed)
                    )
                finally:
                    loop.close()
                return
        
        # Use stored loop
        if loop.is_running():
            # Loop is running in another thread/context, schedule as task
            asyncio.run_coroutine_threadsafe(
                self.send_wheel_speed_command(left_speed, right_speed),
                loop
            )
        else:
            # Loop exists but not running, run until complete
            loop.run_until_complete(
                self.send_wheel_speed_command(left_speed, right_speed)
            )

