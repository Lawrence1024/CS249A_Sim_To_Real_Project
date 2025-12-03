# Hardware Interface for Pololu Robots

This module provides a simple interface for controlling physical Pololu robots via Bluetooth Low Energy (BLE) and receiving position/orientation feedback from motion capture systems.

## Components

### HardwareInterface (`interface.py`)

A Python class that wraps BLE and mocap interfaces:

- **BLE Control**: Sends motor commands to the robot via Bluetooth
- **Mocap Feedback**: Receives position and orientation from motion capture system

### HardwarePololuRobot (`model.scenic`)

A Scenic robot class that extends `PololuRobot` with hardware integration:

- Sends motor commands via BLE when `setMotors()` is called
- Updates position/orientation from mocap system
- Works seamlessly with Scenic behaviors

## Usage

### 1. Initialize Hardware Interface

```python
import asyncio
from scenic.hardware.pololu import HardwareInterface

async def main():
    # Create hardware interface
    interface = HardwareInterface(mocap_target_id=15)
    
    # Connect to BLE device
    if not await interface.connect():
        print("Failed to connect to BLE device")
        return
    
    # Use the interface...
    
    # Disconnect when done
    await interface.disconnect()
```

### 2. Use in Scenic Scenario

```scenic
# pololu_hardware.scenic
model scenic.hardware.pololu.model
from scenic.domains.robotics.behaviors import SquareTrackBehavior

# Create hardware robot
robot = new HardwarePololuRobot at (0, 0, 0), 
    with behavior SquareTrackBehavior(forwardSpeed=80, turnSpeed=60)
```

### 3. Integration Pattern

The typical integration pattern connects Scenic scenarios with hardware:

```python
import asyncio
import scenic
from scenic.hardware.pololu import HardwareInterface

async def run_hardware_scenario():
    # Initialize hardware
    interface = HardwareInterface(mocap_target_id=15)
    if not await interface.connect():
        print("Failed to connect")
        return
    
    # Load Scenic scenario
    scenario = scenic.scenarioFromFile("pololu_hardware.scenic")
    
    # Generate scene
    scene, _ = scenario.generate()
    
    # Set hardware interface on robot
    for obj in scene.objects:
        if hasattr(obj, 'setHardwareInterface'):
            obj.setHardwareInterface(interface)
    
    # Simulation loop
    try:
        while True:
            # Update position from mocap
            for obj in scene.objects:
                if hasattr(obj, 'updatePositionFromMocap'):
                    obj.updatePositionFromMocap()
            
            # Execute Scenic behaviors (which will call setMotors)
            # This triggers motor commands via BLE
            for obj in scene.objects:
                if hasattr(obj, '_pending_motor_command'):
                    cmd = obj.getPendingMotorCommand()
                    if cmd:
                        left, right = cmd
                        await interface.send_wheel_speed_command(left, right)
            
            # Step simulation (if using a simulator loop)
            # ... your simulation step logic ...
            
            await asyncio.sleep(0.01)  # Control loop rate
            
    finally:
        await interface.disconnect()

if __name__ == "__main__":
    asyncio.run(run_hardware_scenario())
```

## API Reference

### HardwareInterface

#### `__init__(mocap_target_id=15)`
Initialize hardware interface with mocap target ID.

#### `async connect() -> bool`
Connect to BLE device. Returns True if successful.

#### `async send_wheel_speed_command(left_speed: float, right_speed: float)`
Send wheel speed command via BLE.
- **left_speed**: Speed for left wheel (-255 to 255)
- **right_speed**: Speed for right wheel (-255 to 255)

#### `get_pose() -> Pose`
Get current pose from mocap system. Returns a `Pose` object with:
- Position: `x`, `y`, `z` (meters)
- Orientation: `qx`, `qy`, `qz`, `qw` (quaternion)

#### `async disconnect()`
Disconnect from BLE device.

### HardwarePololuRobot

#### `setHardwareInterface(interface)`
Set the hardware interface for this robot.

#### `updatePositionFromMocap()`
Update robot position and orientation from mocap system.

#### `getPendingMotorCommand() -> Tuple[int, int] | None`
Get and clear any pending motor command. Returns `(left_speed, right_speed)` in BLE range (-255 to 255).

## Speed Conversion

- **Scenic range**: -100 to 100 (used by behaviors)
- **BLE range**: -255 to 255 (hardware interface)

The conversion is automatic: `ble_speed = (scenic_speed / 100.0) * 255`

## Notes

- The hardware interface must be connected before sending commands
- Position updates from mocap should be called regularly in the control loop
- Motor commands are queued and should be sent asynchronously by the simulation loop
- The interface handles async operations internally and provides a clean API

