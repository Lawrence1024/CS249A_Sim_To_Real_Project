# Webots Robotics Simulator Integration Documentation

## Overview

This document explains how the Scenic Webots robotics simulator works, including the complete flow from scenario compilation to robot behavior execution. The architecture demonstrates a clean separation between generic robotics domain concepts and Webots-specific simulator integration.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│  Scenario File (simple_robot.scenic)                    │
│  - Uses Webots robotics model                           │
│  - Defines robot with behavior                          │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Webots Robotics Model (robotics_model.scenic)         │
│  - WebotsRobot, WebotsPololuRobot                      │
│  - Inherits from both:                                  │
│    1. WebotsObject (Webots node integration)           │
│    2. DifferentialDriveRobot (generic robotics)        │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Generic Robotics Domain (domains/robotics/)            │
│  - Robot, DifferentialDriveRobot classes               │
│  - Actions: MoveForward, TurnLeft, etc.                │
│  - Behaviors: RandomWalk, LineFollowing, etc.          │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Webots Simulator (simulators/webots/)                 │
│  - WebotsSimulator, WebotsSimulation                   │
│  - Supervisor API integration                          │
│  - Coordinate system transformations                   │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Webots Robotics Simulator                              │
│  - Physics engine, motors, sensors                     │
└─────────────────────────────────────────────────────────┘
```

## Complete Data Flow

### 1. Scenario Compilation

**Entry Point:** `examples/webots/robotics/webots_data/controllers/scenic_supervisor/scenic_supervisor.py`

```python
# Webots supervisor controller loads and compiles Scenic scenario
scenario = scenic.scenarioFromFile(path)  # Compiles .scenic file

# Configuration:
# - .wbt world file defines supervisor with customData pointing to .scenic file
# - Supervisor controller = "scenic_supervisor" (Python script)
# - customData = "../../../simple_robot.scenic"
```

**Model Loading:**
```scenic
# simple_robot.scenic imports:
model scenic.simulators.webots.robotics_model
from scenic.domains.robotics.behaviors import RandomWalkBehavior
```

**Model Chain:**
1. `robotics_model.scenic` imports:
   - `from scenic.domains.robotics.model import *` → Generic robot classes
   - `from scenic.simulators.webots.model import WebotsObject` → Webots-specific base
2. Defines `WebotsRobot(WebotsObject, DifferentialDriveRobot)` bridge class
3. Provides `WebotsPololuRobot`, `WebotsLineFollowingRobot` specializations

### 2. Scene Generation

```python
# Each simulation loop:
scene, _ = scenario.generate()  # Samples initial scene
simulator.simulate(scene, verbosity=2)  # Runs dynamic simulation
```

**Scene Contents:**
- Robot objects with initial positions/orientations
- Behaviors attached to robots
- Environment objects (ground, obstacles, etc.)

### 3. Simulation Initialization

**WebotsSimulator Setup:**
- Reads WorldInfo node from .wbt file
- Determines coordinate system (ENU, NUE, EUN)
- Creates WebotsSimulation instance

**WebotsSimulation Setup:**
- Maps Scenic objects to Webots nodes
- Sets initial positions/orientations via Supervisor API
- Configures robot controllers
- Creates ad-hoc objects if needed

**Object Creation:**
```python
# For each object in scene:
def createObjectInSimulator(self, obj):
    # Find matching Webots node by webotsName or webotsType
    webotsObj = self.supervisor.getFromDef(name)
    obj.webotsObject = webotsObj
    obj.webotsSupervisor = self.supervisor  # For motor commands
    
    # Set initial properties
    pos = self.coordinateSystem.positionFromScenic(obj.position)
    webotsObj.getField("translation").setSFVec3f(pos)
    # ... orientation, density, etc.
```

### 4. Behavior Execution Flow

**Complete Action Chain:**

```
┌──────────────────────────────────────────────────┐
│ RandomWalkBehavior (generic robotics domain)     │
│ while True:                                      │
│   do MoveForwardAction(forwardSpeed) for 2s      │
│   do TurnLeft/TurnRight for 1s                   │
└──────────────────────────────────────────────────┘
                        ↓ takes actions
┌──────────────────────────────────────────────────┐
│ MoveForwardAction.applyTo(obj, sim)             │
│   obj.setMotors(self.speed, self.speed)         │
└──────────────────────────────────────────────────┘
                        ↓ calls
┌──────────────────────────────────────────────────┐
│ WebotsRobot.setMotors(left, right)              │
│   self.setLeftMotor(left)                       │
│   self.setRightMotor(right)                     │
└──────────────────────────────────────────────────┘
                        ↓ each calls
┌──────────────────────────────────────────────────┐
│ WebotsRobot.setLeftMotor(speed)                 │
│   super().setLeftMotor(speed)  # Updates property│
│   self._sendMotorCommand()     # Sends to Webots│
└──────────────────────────────────────────────────┘
                        ↓ calls
┌──────────────────────────────────────────────────┐
│ WebotsRobot._sendMotorCommand()                 │
│   - Scales speeds to Webots limits              │
│   - Creates JSON command                        │
│   - emitter.send(command) → robot controller    │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────┐
│ Robot Controller (simple_robot_controller.py)   │
│   - Receives JSON command                       │
│   - Sets motor velocities                      │
└──────────────────────────────────────────────────┘
```

### 5. Simulation Loop (per timestep)

```python
# In Simulation._run():
while True:
    # 1. Run behaviors to get actions
    for agent in schedule:
        actions = agent.behavior._step()
        allActions[agent] = actions
    
    # 2. Execute actions
    self.executeActions(allActions)  # Calls action.applyTo()
    
    # 3. Step simulator
    self.step()  # WebotsSimulation calls supervisor.step()
    
    # 4. Update object properties from simulator
    self.updateObjects()  # Reads positions, velocities, etc.
```

**WebotsSimulation.step():**
```python
def step(self):
    # Actions already executed in parent class
    self._collectAndExecuteActions()  # For custom action handling
    
    # Advance Webots physics
    ms = round(1000 * self.timestep)
    self.supervisor.step(ms)
```

### 6. Communication Mechanism

**Supervisor → Robot Controller:**
```python
# In WebotsRobot._sendMotorCommand():
emitter = self.webotsSupervisor.getDevice("emitter")
command = {
    "type": "motor_command",
    "left_speed": scaled_left,
    "right_speed": scaled_right
}
emitter.send(json.dumps(command).encode('utf-8'))
```

**Robot Controller Receives:**
```python
# In robot controller:
if self.receiver.getQueueLength() > 0:
    message = self.receiver.getString()
    command = json.loads(message)
    if command.get("type") == "motor_command":
        self.left_motor.setVelocity(-float(left_speed))
        self.right_motor.setVelocity(-float(right_speed))
```

### 7. Property Updates

**Reading State from Webots:**
```python
def getProperties(self, obj, properties):
    webotsObj = obj.webotsObject
    pos = webotsObj.getField("translation").getSFVec3f()
    # Convert to Scenic coordinates
    x, y, z = self.coordinateSystem.positionToScenic(pos)
    lx, ly, lz, ax, ay, az = webotsObj.getVelocity()
    # ... return dict of current properties
```

## Key Integration Points

### Point 1: Multiple Inheritance Bridge

```python
# robotics_model.scenic
class WebotsRobot(WebotsObject, DifferentialDriveRobot):
    """Combines Webots integration with robotics domain."""
    
    def setLeftMotor(self, speed):
        super().setLeftMotor(speed)  # Domain update
        self._sendMotorCommand()      # Simulator send
```

**Why this design:**
- `WebotsObject` provides Webots node matching and Supervisor access
- `DifferentialDriveRobot` provides motor interface and domain semantics
- `WebotsRobot` adds the bridge code to send commands to simulator

### Point 2: Simulator Wiring

```python
# In createObjectInSimulator():
obj.webotsObject = webotsObj           # Node handle
obj.webotsSupervisor = self.supervisor # For Emitter access
obj.webotsName = name                   # Node identifier
```

These attributes enable the robot to:
- Access its Webots node directly
- Send motor commands via Emitter
- Receive state updates from Webots

### Point 3: Action Polymorphism

```python
# Generic action (works with any robot type):
class MoveForwardAction(Action):
    def applyTo(self, obj, sim):
        obj.setMotors(self.speed, self.speed)

# Robot must implement setMotors:
class DifferentialDriveRobot:
    def setMotors(self, left, right):
        self.setLeftMotor(left)
        self.setRightMotor(right)

# WebotsRobot adds simulator integration:
class WebotsRobot:
    def setLeftMotor(self, speed):
        super().setLeftMotor(speed)  # Updates property
        self._sendMotorCommand()     # Sends command
```

**Benefits:**
- Behaviors are simulator-agnostic
- Actions work with any DifferentialDriveRobot
- Simulator-specific code isolated to WebotsRobot

### Point 4: Model Statement Loading

```python
# Scenic's model statement (in veneer.py):
def model(namespace, modelName):
    module = importlib.import_module(modelName)
    # Import all non-underscore names into current namespace
    for name, value in module.__dict__.items():
        if not name.startswith("_"):
            namespace[name] = value
```

**Result:**
```scenic
model scenic.simulators.webots.robotics_model
# Now available:
# - WebotsPololuRobot, WebotsLineFollowingRobot
# - WebotsMaze, WebotsTrack, etc.
# - All classes from domains.robotics imported by the model
```

## File Structure

```
Scenic/
├── src/scenic/
│   ├── domains/robotics/
│   │   ├── model.scenic           # Generic robot classes
│   │   ├── actions.py             # Motor control actions
│   │   ├── behaviors.scenic       # Robot behaviors
│   │   └── __init__.py
│   └── simulators/webots/
│       ├── simulator.py           # Core simulation loop
│       ├── model.scenic           # Generic Webots integration
│       ├── robotics_model.scenic  # Webots robotics bridge
│       ├── actions.py             # Webots-specific actions
│       └── utils.py               # Coordinate conversions
├── examples/webots/robotics/
│   ├── simple_robot.scenic        # Example scenario
│   ├── line_following.scenic      # Example scenario
│   └── webots_data/
│       ├── worlds/
│       │   └── simple_robot.wbt   # Webots world file
│       └── controllers/
│           ├── scenic_supervisor/
│           │   └── scenic_supervisor.py  # Supervisor controller
│           └── simple_robot_controller/
│               └── simple_robot_controller.py  # Robot controller
```

## Configuration Example

**simple_robot.scenic:**
```scenic
model scenic.simulators.webots.robotics_model
from scenic.domains.robotics.behaviors import RandomWalkBehavior

robot = new WebotsPololuRobot at (0, 0, 0.016), facing 90 deg, 
    with behavior RandomWalkBehavior()

terminate after 30 seconds
```

**simple_robot.wbt (key parts):**
```wbt
Robot {
  name "Supervisor"
  controller "scenic_supervisor"
  customData "../../../simple_robot.scenic"
  supervisor TRUE
  children [
    Emitter { channel 1 }
    Receiver { channel 1 }
  ]
}

DEF POLOLU_ROBOT Robot {
  controller "simple_robot_controller"
  children [
    HingeJoint {
      device [RotationalMotor { name "leftMotor" }]
    }
    HingeJoint {
      device [RotationalMotor { name "rightMotor" }]
    }
    Emitter { channel 1 }
    Receiver { channel 1 }
  ]
}
```

## Design Principles

### 1. Separation of Concerns
- **Domain Layer:** Simulator-agnostic robot concepts, behaviors, actions
- **Simulator Layer:** Webots-specific integration code
- **Bridge Layer:** Connects domain to simulator

### 2. Simulator Agnostic Behaviors
Behaviors like `RandomWalkBehavior` don't know about Webots:
- They use generic actions (`MoveForwardAction`)
- Actions call generic robot methods (`setMotors`)
- Only the `WebotsRobot` implementation knows about Emitter/Receiver

### 3. Inheritance-Based Extension
```python
Robot → DifferentialDriveRobot → PololuRobot
WebotsObject → WebotsRobot → WebotsPololuRobot
              ↑                    ↑
        (inherits from both DifferentialDriveRobot and WebotsObject)
```

### 4. Property-Based Communication
```python
# Actions update robot properties
obj.leftMotorSpeed = 50
obj.rightMotorSpeed = 50

# Then trigger side effect
self._sendMotorCommand()  # Sends to simulator
```

This pattern allows:
- Property monitoring and debugging
- Replay of simulation state
- Testing without simulator

## Extending the System

### Adding New Robot Types

```scenic
# In robotics_model.scenic:
class WebotsMyRobot(WebotsRobot):
    webotsName: "MY_ROBOT"
    # Add robot-specific properties/methods
```

### Adding New Behaviors

```scenic
# In domains/robotics/behaviors.scenic:
behavior MyBehavior(speed=50):
    while True:
        take MoveForwardAction(speed)
        # ... custom logic
```

### Adding New Actions

```python
# In domains/robotics/actions.py:
class CustomAction(Action):
    def applyTo(self, obj, sim):
        # Must use generic robot interface
        obj.setMotors(left, right)
        # Or raise if not supported
```

## Troubleshooting

### Robot Not Moving
1. Check `webotsSupervisor` is set in object
2. Verify Emitter/Receiver channels match (default: 1)
3. Check robot controller receives messages
4. Verify motors are enabled in robot controller
5. Check scaling: Scenic uses -100 to 100, Webots may use different range

### Objects Not Found
1. Verify `webotsName` or `webotsType` matches DEF name in .wbt
2. Check object exists in world file
3. Verify world file loads correctly in Webots

### Communication Issues
1. Emitter/Receiver must be on same channel
2. Receiver must be enabled with timestep
3. JSON formatting must match exactly
4. Check supervisor has Emitter/Receiver devices

## Summary

The Webots robotics integration demonstrates:
1. **Clean architecture** with layered domain/simulator separation
2. **Multiple inheritance** to combine capabilities
3. **Polymorphic actions** that work with any robot type
4. **Property-based updates** with side-effect triggers
5. **Simulator-agnostic behaviors** for portability

The key insight is that `WebotsRobot` acts as a bridge, implementing the generic robot interface (`DifferentialDriveRobot`) while adding Webots-specific communication (`WebotsObject` + Emitter/Receiver). This allows behaviors and actions to remain simulator-agnostic while still providing full control over the simulator.

