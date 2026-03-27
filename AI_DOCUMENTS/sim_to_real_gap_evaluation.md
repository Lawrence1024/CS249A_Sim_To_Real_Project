# Sim-to-Real Gap Evaluation System for Pololu Racing

## Overview

This project implements a comprehensive system for evaluating the sim-to-real gap in robotic systems, specifically focusing on Pololu 3Pi+ 2040 robot time trial racing. The system enables automated comparison between simulation (Webots) and real hardware performance, using a Multi-Armed Bandit (MAB) sampler to intelligently explore parameter spaces and identify regions with high sim-to-real discrepancies.

### Core Objective

**Evaluate the sim-to-real gap** by:
1. Running identical Scenic scenarios in both simulation (Webots) and real hardware
2. Collecting trajectory and performance data from both runs
3. Computing quantitative gap metrics (waypoint accuracy, boundary violations, trajectory alignment)
4. Feeding gap metrics back to an MAB sampler to guide future parameter selection
5. Iteratively refining the parameter space to find regions of high discrepancy

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Scenic Robotics Domain                        │
│  (Generic behaviors, actions, robot models - simulator agnostic) │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
    ┌───────────▼──────────┐    ┌───────────▼──────────┐
    │   Webots Simulation  │    │   Hardware Control   │
    │   (Digital Twin)     │    │   (Real Robot)       │
    └───────────┬──────────┘    └───────────┬──────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                ┌─────────────▼─────────────┐
                │   Post-Processing & Gap   │
                │   Metric Computation      │
                └─────────────┬─────────────┘
                              │
                ┌─────────────▼─────────────┐
                │   MAB Sampler             │
                │   (Parameter Selection)   │
                └───────────────────────────┘
```

---

## Part 1: Robotics Domain Definition

**Location:** `Scenic/src/scenic/domains/robotics/`

The robotics domain provides a **simulator-agnostic** foundation for robot behaviors and actions. This abstraction allows the same behaviors to work in both simulation and real hardware.

### Components

#### 1. Robot Models (`model.scenic`)

Defines the robot class hierarchy:

```scenic
Robot (base class)
  └── DifferentialDriveRobot (left/right motor control)
       └── PololuRobot (Pololu-specific dimensions)
            ├── LineFollowingRobot
            └── ObstacleAvoidanceRobot
```

**Key Properties:**
- `position`: 3D position (x, y, z)
- `heading`: Orientation angle
- `leftMotorSpeed`, `rightMotorSpeed`: Motor speeds (-100 to 100)
- Physical dimensions: Based on Pololu 3Pi+ 32U4 OLED official drawings
  - Body: 91.2mm × 66mm × 26.1mm
  - Wheels: 32mm diameter, 6.8mm width
  - Ground clearance: 5.8mm

#### 2. Actions (`actions.py`)

Actions are commands that robots can execute:

- **`MoveForwardAction(speed)`**: Move forward at given speed
- **`MoveBackwardAction(speed)`**: Move backward
- **`TurnLeftAction(speed)`**: Rotate left (counter-clockwise)
- **`TurnRightAction(speed)`**: Rotate right (clockwise)
- **`StopAction()`**: Stop all motors
- **`SetMotorAction(left, right)`**: Set individual motor speeds
- **`TurnByAngleAction(angle, speed)`**: Turn by specific angle

**Action Interface:**
```python
class Action:
    def applyTo(self, obj, sim):
        # obj must implement setMotors(left, right)
        obj.setMotors(self.left, self.right)
```

#### 3. Behaviors (`behaviors.scenic`)

Behaviors define high-level robot strategies:

**`SquareTrackBehavior(forwardSpeed, turnSpeed, waypointThreshold, headingOffset)`**
- Follows a square racetrack defined by 4 waypoints
- Uses proportional control to navigate between waypoints
- Continuously loops around the track

**`PatrolBehavior(waypoints, forwardSpeed, turnSpeed, waypointThreshold, headingOffset)`**
- Generic waypoint-following behavior
- Uses improved proportional control with non-linear response
- Adjusts motor speeds based on angle error to target

**Key Behavior Pattern:**
```scenic
behavior PatrolBehavior(waypoints, forwardSpeed=50, turnSpeed=40):
    currentWaypoint = 0
    while True:
        target = waypoints[currentWaypoint]
        angle = headingOfSegment(self.position, target) - self.heading
        distance = distance from self to target
        
        if distance > waypointThreshold:
            # Proportional control to adjust motor speeds
            take SetMotorAction(leftSpeed, rightSpeed)
            wait
        else:
            # Reached waypoint, move to next
            currentWaypoint = (currentWaypoint + 1) % len(waypoints)
            wait
```

**Logging:**
Behaviors log trajectory data using `FastLogger`:
- Timestamp (nanoseconds)
- Step count
- Position (x, y, z)
- Headings (current, target, effective, error)
- Target waypoint ID

---

## Part 2: Simulation Side (Webots Digital Twin)

**Location:** 
- `Scenic/src/scenic/simulators/webots/robotics_model.scenic`
- `Scenic/examples/webots/robotics/`

### Architecture

The Webots integration bridges the generic robotics domain with Webots-specific simulation:

```
Generic Robotics Domain
    ↓ (inheritance)
WebotsRobot (bridge class)
    ↓ (inheritance)
WebotsPololuRobot
```

### Key Components

#### 1. Webots Robotics Model (`robotics_model.scenic`)

**`WebotsRobot(WebotsObject, DifferentialDriveRobot)`**
- Combines Webots node integration with differential drive capabilities
- Overrides `setLeftMotor()` and `setRightMotor()` to send commands to Webots

**Motor Command Flow:**
```python
def setLeftMotor(self, speed):
    super().setLeftMotor(speed)  # Update Scenic property
    self._sendMotorCommand()      # Send to Webots

def _sendMotorCommand(self):
    # Scale to Webots limits (maxVelocity = 50 rad/s)
    scaled_left = (self.leftMotorSpeed / 100.0) * 50
    scaled_right = (self.rightMotorSpeed / 100.0) * 50
    
    # Send JSON command via Emitter
    command = {
        "type": "motor_command",
        "left_speed": scaled_left,
        "right_speed": scaled_right
    }
    emitter.send(json.dumps(command).encode('utf-8'))
```

**Communication:**
- Uses Webots `Emitter`/`Receiver` devices (channel 1)
- Supervisor sends commands to robot controller
- Robot controller receives and applies motor velocities

#### 2. Digital Twin Specifications

**Critical Requirement:** The digital twin must match the physical robot with **millimeter precision**.

**Physical Dimensions (from engineering drawings):**
- Body: 91.2mm length × 66mm width × 26.1mm height
- Wheels: 32mm diameter, 6.8mm width
- Ball caster: 12.7mm diameter
- Ground clearance: 5.8mm
- Wheelbase: ~66mm (center-to-center)

**World File Configuration:**
- Robot node: `DEF POLOLU_ROBOT Robot`
- Motors: `RotationalMotor` with `maxVelocity = 50` rad/s
- Coordinate system: ENU (East-North-Up)
- Supervisor: Loads Scenic scenario from `customData`

**See:** `Scenic/examples/webots/robotics/DIGITAL_TWIN_SPECIFICATIONS.md` for detailed measurements

#### 3. Scenario Files

**`pololu.scenic`**: Square racetrack scenario
```scenic
model scenic.simulators.webots.robotics_model
from scenic.domains.robotics.behaviors import SquareTrackBehavior

robot = new WebotsPololuRobot at (-1.268, -0.737, 0.01885), 
    with behavior SquareTrackBehavior(
        forwardSpeed=35.944127, 
        turnSpeed=25.614439, 
        waypointThreshold=0.119377,
        headingOffset=-90 deg
    )
```

**Parameters:**
- `forwardSpeed`: Base forward speed (0-100)
- `turnSpeed`: Maximum turn speed adjustment (0-100)
- `waypointThreshold`: Distance to consider waypoint reached (meters)
- `headingOffset`: Heading calibration offset (degrees)

#### 4. Webots Integration Flow

1. **World File Loads**: `.wbt` file defines robot and supervisor
2. **Supervisor Controller**: `scenic_supervisor.py` loads Scenic scenario
3. **Scene Generation**: Scenic samples initial scene
4. **Object Mapping**: Scenic objects mapped to Webots nodes via `webotsName`
5. **Behavior Execution**: Behaviors generate actions
6. **Command Transmission**: Actions → motor commands → Emitter → Robot controller
7. **State Updates**: Webots physics updates, positions read back to Scenic

**See:** `Scenic/AI_DOCUMENTS/webots_robotics_integration.md` for detailed flow

---

## Part 3: Real Hardware Side

**Location:**
- `Scenic/src/scenic/hardware/pololu/`
- `Scenic/pololu_bluetooth_testing/`
- `Scenic/pololu-3pi-2040/`
- `Scenic/mocap/`

### Architecture

The hardware integration provides the same interface as simulation:

```
Generic Robotics Domain
    ↓ (inheritance)
HardwarePololuRobot
    ↓ (uses)
HardwareInterface (BLE + Mocap)
```

### Key Components

#### 1. Hardware Interface (`interface.py`)

**`HardwareInterface`** wraps two subsystems:

**Bluetooth Low Energy (BLE):**
- Connects to Pololu robot via BLE
- Sends motor commands as angular velocities (deg/s)
- Converts Scenic speeds (0-100) to hardware format

**Motion Capture (Mocap):**
- Receives position and orientation from OptiTrack/NatNet
- Provides pose updates to Scenic objects
- Target ID: 15 (configurable)

**Speed Conversion:**
```python
# Scenic: 0-100 range
# Hardware: angular velocity in deg/s
left_angular_vel = (left_speed / 100.0) * max_angular_velocity
left_angular_vel = left_angular_vel * (180.0 / π)  # rad/s → deg/s
```

#### 2. Hardware Robot Model (`model.scenic`)

**`HardwarePololuRobot(PololuRobot)`**
- Extends generic PololuRobot with hardware integration
- Queues motor commands for async execution
- Updates position from mocap system

**Motor Command Flow:**
```python
def setLeftMotor(self, speed):
    super().setLeftMotor(speed)  # Update Scenic property
    self._sendMotorCommand()     # Queue for hardware

def _sendMotorCommand(self):
    # Store command to be sent asynchronously
    self._pending_motor_command = (left_speed, right_speed)
```

**Position Updates:**
```python
def updatePositionFromMocap(self):
    pose = self._hardware_interface.get_pose()
    self.position = Vector(pose.x, pose.y, pose.z)
    
    # Convert quaternion to heading
    euler = pose.get_euler_zyx(degrees=False)
    yaw = euler[0]
    
    # Convert to Scenic coordinate system
    self.heading = normalizeAngle(yaw - π/2)
```

#### 3. Hardware Simulator (`simulator.py`)

**`HardwareSimulator`** creates `HardwareSimulation` instances:

**Simulation Loop:**
```python
def step(self):
    # 1. Send pending motor commands to hardware
    for agent in self.agents:
        cmd = agent.getPendingMotorCommand()
        if cmd:
            left, right = cmd
            self.interface.send_wheel_speed_command_sync(left, right)
    
    # 2. Wait for real-world timestep
    time.sleep(self.timestep)
    
    # 3. Update properties from mocap
    for obj in self.objects:
        if hasattr(obj, "updatePositionFromMocap"):
            obj.updatePositionFromMocap()
```

**Key Differences from Webots:**
- No physics simulation (real world is the simulator)
- Async BLE communication handled via event loop
- Position updates come from mocap, not physics engine
- Timestep is real wall-clock time

#### 4. BLE Communication (`pololu_bluetooth_testing/`)

**`PololuBLE`** class:
- Discovers and connects to Pololu robot via BLE
- Sends motor commands as binary packets
- Format: `struct.pack('<cff', b'A', left_deg_per_s, right_deg_per_s)`

**Robot Firmware:**
- Runs on Raspberry Pi Pico (RP2040)
- Receives BLE commands
- Controls motors via PWM
- Located in `Scenic/pololu-3pi-2040/`

#### 5. Motion Capture System (`mocap/`)

**`MocapEstimator`**:
- Connects to OptiTrack Motive via NatNet protocol
- Receives rigid body pose updates
- Provides `get_pose()` returning position and quaternion

**Configuration:**
- Server IP: 169.254.10.221 (Motive machine)
- Client IP: 169.254.10.222 (Control computer)
- Target ID: 15 (Pololu robot marker set)

**Coordinate System:**
- Mocap provides position in meters
- Orientation as quaternion (qx, qy, qz, qw)
- Converted to Scenic heading (yaw angle)

#### 6. Hardware Scenario

**`pololu_hardware.scenic`**:
```scenic
model scenic.hardware.pololu.model
from scenic.domains.robotics.behaviors import SquareTrackBehavior

robot = new HardwarePololuRobot at (0, 0, 0), 
    with behavior SquareTrackBehavior(
        forwardSpeed=80, 
        turnSpeed=60
    )
```

**Execution:**
```python
# run_pololu_hardware.py
interface = HardwareInterface(mocap_target_id=15)
await interface.connect()

scenario = scenic.scenarioFromFile("pololu_hardware.scenic")
simulator = HardwareSimulator(interface, timestep=0.02)
simulation = simulator.createSimulation(scene)
simulation.run()
```

---

## Part 4: Post-Processing and Gap Metric Computation

**Location:** `Scenic/examples/webots/robotics/sampler/`

### Overview

After running both simulation and hardware with the same parameters, we compute quantitative metrics to measure the sim-to-real gap.

### Components

#### 1. Log Decoder (`log_decoder.py`)

**`LogDecoder`** decodes binary log files:
- Reads trajectory data from `FastLogger` binary format
- Returns pandas DataFrame with columns:
  - `timestamp`: Nanosecond timestamps
  - `step_count`: Simulation step number
  - `pos`: Position array [x, y, z]
  - `headings`: Heading array [current, target, effective, error]
  - `target_id`: Current waypoint ID

**Usage:**
```python
df = LogDecoder.decode_df("sim_log.bin")
```

#### 2. Gap Analyzer (`gap_analyzer_v2.py`)

**`compute_sim_real_gap_v2()`** computes multiple gap metrics:

**Waypoint Gap:**
- Counts waypoints hit in sim vs. real
- Computes absolute difference
- Normalized: `|waypoints_sim - waypoints_real| / total_waypoints`

**Boundary Violation Gap:**
- Checks if robot stays within track boundaries
- Compares boundary violations between sim and real
- Binary match: 1 if both violate or both don't, 0 otherwise

**Trajectory Gap:**
- Aligns sim and real trajectories using dynamic time warping
- Computes point-to-point distance after alignment
- Normalized by `trajectory_norm` (default: 0.2 meters)

**Configuration:**
```python
config = TrajectoryGapConfig(
    use_relative_deltas=False,      # Use absolute distances
    trajectory_norm=0.2,            # Normalization factor (meters)
    boundary_limit_dist=0.25        # Boundary check distance (meters)
)
```

#### 3. Post-Processing (`post_processing.py`)

**`compute_gap_metric()`** combines all metrics into a single error value:

**Metrics:**
```python
metrics = {
    "waypoints_hit_sim": int,           # Waypoints hit in simulation
    "waypoints_hit_real": int,           # Waypoints hit in hardware
    "waypoints_diff": int,               # Absolute difference
    "boundary_violation_sim": bool,      # Boundary violation in sim
    "boundary_violation_real": bool,     # Boundary violation in real
    "boundary_match": int,               # 1 if match, 0 if mismatch
    "trajectory_gap_raw": float,         # Raw trajectory distance
    "normalized_waypoint_gap": float,    # Normalized waypoint error
    "normalized_boundary_gap": float,    # Normalized boundary error
    "normalized_trajectory_gap": float,  # Normalized trajectory error
    "combined_error": float              # Final combined metric [0, 1]
}
```

**Combined Error Formula:**
```python
if waypoint_gap == 0:
    # If waypoints match, focus on boundary and trajectory
    combined_error = min(1.0,
        weights["boundary"] * boundary_gap +
        weights["trajectory"] * trajectory_gap
    )
else:
    # If waypoints differ, prioritize waypoint accuracy
    combined_error = min(1.0,
        weights["waypoint"] * waypoint_gap +
        weights["boundary_wp_diff"] * boundary_gap
    )
```

**Default Weights:**
```python
DEFAULT_WEIGHTS = {
    "waypoint": 0.8,           # High weight for waypoint accuracy
    "boundary_wp_diff": 0.2,    # Lower weight when waypoints differ
    "boundary": 0.6,            # Medium weight for boundary violations
    "trajectory": 0.4           # Lower weight for trajectory alignment
}
```

**Usage:**
```python
metrics = compute_gap_metric(
    sim_log_file="sim_log.bin",
    real_log_file="real_log.bin",
    do_visualize=False,
    weights=DEFAULT_WEIGHTS
)

combined_error = metrics["combined_error"]  # [0, 1], higher = larger gap
```

#### 4. Boundary Check (`boundary_check.py`)

Validates robot stays within track boundaries:
- Checks if position is within outer boundary
- Checks if position is outside inner boundary (for track)
- Returns boolean violation status

---

## Part 5: MAB Sampler for Parameter Selection

**Location:** `Scenic/examples/webots/robotics/sampler/sampler.py`

### Overview

The Multi-Armed Bandit (MAB) sampler intelligently selects parameter configurations to test, focusing exploration on regions with high sim-to-real gap.

### Architecture

**Inspired by VerifAI:** The sampler uses Upper Confidence Bound (UCB) algorithm to balance exploration and exploitation.

### Components

#### 1. Sampler Base Class

**`Sampler`** abstract base:
```python
class Sampler:
    def getSample(self):
        """Generate next parameter sample."""
        raise NotImplementedError
    
    def update(self, sample, error_value):
        """Update sampler with gap metric."""
        raise NotImplementedError
```

#### 2. Multi-Armed Bandit Sampler

**`MultiArmedBanditSampler`** implements UCB algorithm:

**Initialization:**
```python
sampler = MultiArmedBanditSampler(
    domain=parameter_domain,      # Parameter ranges
    alpha=0.1,                     # Learning rate (unused in MAB)
    thres=0.0,                     # Threshold (unused in MAB)
    buckets=10,                   # Discretization buckets per parameter
    exploration_ratio=2.0          # UCB exploration constant
)
```

**Parameter Domain:**
```python
domain = {
    "forwardSpeed": Interval(30, 70),      # Forward speed range
    "turnSpeed": Interval(20, 40),          # Turn speed range
    "waypointThreshold": Interval(0.08, 0.12)  # Waypoint threshold range
}
```

**Sample Generation (UCB):**
```python
def getSample(self):
    # Compute UCB for each bucket
    for feature in domain.keys():
        proportions = errors[feature] / counts[feature]
        ucb = proportions + sqrt(exploration_ratio * log(t) / counts[feature])
        
        # Select bucket with highest UCB
        bucket = argmax(ucb)
        
        # Sample uniformly within bucket
        value = sample_uniform(bucket_range)
    
    return parameter_dict
```

**Update (Learning):**
```python
def update(self, sample, error_value):
    """Update sampler with gap metric."""
    self.t += 1
    
    for feature in domain.keys():
        bucket = sampleToBucket(sample[feature])
        self.counts[feature][bucket] += 1
        self.errors[feature][bucket] += error_value  # Accumulate error
```

**Key Properties:**
- **Exploration**: UCB encourages trying unexplored regions
- **Exploitation**: Focuses on regions with high error (large gap)
- **Discretization**: Parameters discretized into buckets for tractability
- **Multi-dimensional**: Handles multiple parameters simultaneously

#### 3. Cross-Entropy Sampler (Alternative)

**`CrossEntropySampler`** uses cross-entropy method:
- Maintains probability distribution over buckets
- Updates distribution based on samples above threshold
- Less exploration-focused than MAB

**Use Case:** When you want to focus on high-error regions more aggressively.

#### 4. Integration with Evaluation Loop

**Manual Evaluation Flow:**
```python
# 1. Get sample from sampler
params = sampler.getSample()

# 2. Update Scenic scenario files with parameters
update_scenic_files(params)

# 3. Run simulation (manual or automated)
run_webots_simulation()  # Produces sim_log.bin

# 4. Run hardware (manual)
run_hardware_scenario()  # Produces real_log.bin

# 5. Compute gap metric
metrics = compute_gap_metric("sim_log.bin", "real_log.bin")
error = metrics["combined_error"]

# 6. Update sampler
sampler.update(params, error)

# 7. Repeat
```

**Automated Flow (Future):**
- Integrate with `manual_robotics_eval.py`
- Automatically run both sim and hardware
- Compute metrics and update sampler
- Continue until convergence or max iterations

#### 5. State Persistence

**Save/Load Sampler State:**
```python
# Save
sampler.save_state("checkpoints/sampler_state.pkl")

# Load
sampler = MultiArmedBanditSampler.load_state("checkpoints/sampler_state.pkl")
```

**State Includes:**
- Distribution/counts/errors for each parameter
- Bucket configuration
- Domain definition
- Exploration parameters

---

## Part 6: Complete Workflow

### End-to-End Process

1. **Initialize Sampler**
   ```python
   domain = {
       "forwardSpeed": Interval(30, 70),
       "turnSpeed": Interval(20, 40),
       "waypointThreshold": Interval(0.08, 0.12)
   }
   sampler = MultiArmedBanditSampler(domain, buckets=10)
   ```

2. **Get Parameter Sample**
   ```python
   params = sampler.getSample()
   # e.g., {"forwardSpeed": 45.2, "turnSpeed": 28.7, "waypointThreshold": 0.12}
   ```

3. **Update Scenic Files**
   - Modify `pololu.scenic` with sampled parameters
   - Modify `pololu_hardware.scenic` with same parameters

4. **Run Simulation**
   - Launch Webots with `pololu.wbt`
   - Scenario executes, logs trajectory to `sim_log.bin`
   - Simulation runs for fixed duration (e.g., 120 seconds)

5. **Run Hardware**
   - Execute `run_pololu_hardware.py`
   - Robot executes same behavior, logs to `real_log.bin`
   - Hardware run matches simulation duration

6. **Compute Gap Metric**
   ```python
   metrics = compute_gap_metric("sim_log.bin", "real_log.bin")
   error = metrics["combined_error"]  # [0, 1]
   ```

7. **Update Sampler**
   ```python
   sampler.update(params, error)
   ```

8. **Repeat**
   - Sampler selects next parameters (focusing on high-error regions)
   - Process repeats until convergence or max iterations

### Data Flow Diagram

```
┌─────────────┐
│   Sampler   │───[params]───┐
└─────────────┘              │
                              │
                ┌─────────────▼─────────────┐
                │  Update Scenic Files      │
                └─────────────┬─────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
    ┌───────────▼──────────┐    ┌───────────▼──────────┐
    │   Webots Run        │    │   Hardware Run       │
    │   (sim_log.bin)     │    │   (real_log.bin)     │
    └───────────┬──────────┘    └───────────┬──────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                ┌─────────────▼─────────────┐
                │  compute_gap_metric()     │
                │  → combined_error        │
                └─────────────┬─────────────┘
                              │
                ┌─────────────▼─────────────┐
                │  sampler.update(params,   │
                │           error)          │
                └───────────────────────────┘
```

### Key Files and Locations

**Robotics Domain:**
- `Scenic/src/scenic/domains/robotics/model.scenic` - Robot models
- `Scenic/src/scenic/domains/robotics/actions.py` - Actions
- `Scenic/src/scenic/domains/robotics/behaviors.scenic` - Behaviors

**Webots Integration:**
- `Scenic/src/scenic/simulators/webots/robotics_model.scenic` - Webots bridge
- `Scenic/examples/webots/robotics/pololu.scenic` - Simulation scenario
- `Scenic/examples/webots/robotics/webots_data/worlds/pololu.wbt` - World file

**Hardware Integration:**
- `Scenic/src/scenic/hardware/pololu/model.scenic` - Hardware robot model
- `Scenic/src/scenic/hardware/pololu/interface.py` - BLE + Mocap interface
- `Scenic/src/scenic/hardware/pololu/simulator.py` - Hardware simulator
- `Scenic/examples/webots/robotics/pololu_hardware.scenic` - Hardware scenario

**Post-Processing:**
- `Scenic/examples/webots/robotics/sampler/post_processing.py` - Gap computation
- `Scenic/examples/webots/robotics/sampler/gap_analyzer_v2.py` - Trajectory analysis
- `Scenic/examples/webots/robotics/sampler/log_decoder.py` - Log parsing

**Sampling:**
- `Scenic/examples/webots/robotics/sampler/sampler.py` - MAB sampler
- `Scenic/examples/webots/robotics/sampler/manual_robotics_eval.py` - Evaluation loop

**Motion Capture:**
- `Scenic/mocap/mocap_estimator.py` - OptiTrack integration
- `Scenic/mocap/mocap.py` - NatNet client

**Bluetooth:**
- `Scenic/pololu_bluetooth_testing/pololu_ble.py` - BLE communication
- `Scenic/pololu-3pi-2040/` - Robot firmware

---

## Part 7: Key Design Decisions

### 1. Simulator-Agnostic Domain

**Decision:** Separate generic robotics domain from simulator-specific code.

**Rationale:**
- Same behaviors work in simulation and hardware
- Easy to add new simulators (Gazebo, PyBullet, etc.)
- Behaviors are portable and testable

**Implementation:**
- Generic domain in `domains/robotics/`
- Simulator bridges in `simulators/webots/` and `hardware/pololu/`
- Multiple inheritance: `WebotsRobot(WebotsObject, DifferentialDriveRobot)`

### 2. Action-Based Control

**Decision:** Use action objects rather than direct method calls.

**Rationale:**
- Actions can be logged, replayed, and analyzed
- Enables action preconditions and validation
- Supports action composition and sequencing

**Implementation:**
- Actions inherit from `scenic.core.simulators.Action`
- `applyTo(obj, sim)` method called by simulator
- Actions call generic robot methods (`setMotors`)

### 3. Behavior-Driven Execution

**Decision:** Behaviors generate actions, not direct motor commands.

**Rationale:**
- High-level intent (waypoint following) vs. low-level control
- Behaviors are composable and reusable
- Enables behavior switching and adaptation

**Implementation:**
- Behaviors are Scenic `behavior` blocks
- Use `take Action()` to execute actions
- `wait` statement for timing control

### 4. Digital Twin Precision

**Decision:** Match physical robot dimensions to millimeter precision.

**Rationale:**
- Accurate simulation requires accurate model
- Reduces sim-to-real gap from modeling errors
- Enables meaningful gap analysis

**Implementation:**
- Used official Pololu engineering drawings
- Measured all components (body, wheels, caster)
- Validated dimensions in Webots world file

### 5. Unified Logging Format

**Decision:** Use same logging format for sim and hardware.

**Rationale:**
- Enables direct comparison of trajectories
- Same analysis code works for both
- Consistent data structure simplifies gap computation

**Implementation:**
- `FastLogger` binary format
- Logs: timestamp, position, headings, target_id
- Decoded to pandas DataFrame for analysis

### 6. Multi-Metric Gap Analysis

**Decision:** Combine multiple metrics (waypoint, boundary, trajectory) into single error.

**Rationale:**
- Single metric easier for sampler to optimize
- Different metrics capture different aspects of gap
- Weighted combination allows tuning importance

**Implementation:**
- Separate metrics computed independently
- Normalized to [0, 1] range
- Weighted combination with configurable weights

### 7. MAB Sampling Strategy

**Decision:** Use Upper Confidence Bound (UCB) for parameter exploration.

**Rationale:**
- Balances exploration (trying new regions) and exploitation (focusing on high-error regions)
- Handles multi-dimensional parameter spaces
- Converges to regions with largest gap

**Implementation:**
- Discretize parameters into buckets
- Track error accumulation per bucket
- UCB formula: `mean_error + sqrt(exploration_ratio * log(t) / count)`

---

## Part 8: Future Improvements

### 1. Automated Evaluation Loop

**Current:** Manual execution of sim and hardware runs.

**Future:** Fully automated pipeline:
- Sampler generates parameters
- System automatically updates Scenic files
- Launches Webots simulation
- Executes hardware run
- Computes metrics
- Updates sampler
- Repeats until convergence

### 2. Real-Time Gap Monitoring

**Current:** Post-processing after complete runs.

**Future:** Real-time gap computation:
- Compare trajectories as they execute
- Early termination if gap exceeds threshold
- Adaptive parameter adjustment during run

### 3. Multi-Robot Support

**Current:** Single robot time trial.

**Future:** Multi-robot scenarios:
- Multiple robots on track simultaneously
- Collision avoidance behaviors
- Coordinated behaviors

### 4. Sensor Integration

**Current:** Open-loop control (no sensor feedback on Pololu itself).

**Future:** Closed-loop with sensors:
- IR line sensors for line following
- Ultrasonic sensors for obstacle avoidance
- Sensor fusion for robust navigation

### 5. Advanced Sampling Strategies

**Current:** MAB with fixed exploration ratio.

**Future:** Adaptive sampling:
- Bayesian optimization
- Gaussian process regression
- Active learning strategies

---

## Part 9: Experimental Results and Analysis

### Overview

This section presents results from 100 parameter samples collected using the MAB sampler, exploring the three-dimensional parameter space of `forwardSpeed`, `turnSpeed`, and `waypointThreshold`. The analysis reveals critical insights about parameter regions that lead to high sim-to-real gaps and successful lap completion.

### Experimental Setup

- **Total Samples**: 100 parameter configurations
- **Gap Range**: [0.065, 1.000] (combined error metric)
- **Gap Threshold**: 0.60 (30 samples ≥ 0.60, 70 samples < 0.60)
- **Parameter Ranges**:
  - `forwardSpeed`: 28-70
  - `turnSpeed`: 19-40
  - `waypointThreshold`: 0.078-0.122 meters

### Key Findings

#### 1. Overall Gap Distribution

**High Gap Region (≥0.60)**: 30% of samples
- Indicates significant sim-to-real discrepancy
- Often associated with unfinished laps
- Concentrated in specific parameter combinations

**Low Gap Region (<0.60)**: 70% of samples
- Indicates good sim-to-real alignment
- Most successful lap completions fall here
- Represents regions where simulation accurately predicts hardware behavior

#### 2. Forward Speed vs. Tolerance Analysis

**Key Observations:**

**Low Speed, High Tolerance (Top-Left Cluster)**
- `forwardSpeed`: 30-35, `waypointThreshold`: 0.115-0.120
- **Result**: All samples finished laps with low combined error (green)
- **Insight**: Conservative speed with generous tolerance provides reliable, low-gap performance

**Low Speed, Low Tolerance (Bottom-Left Cluster)**
- `forwardSpeed`: 38-42, `waypointThreshold`: 0.080-0.085
- **Result**: All samples finished laps with low combined error
- **Insight**: Moderate speed with tight tolerance can work well if speed is controlled

**Mid-Range Speed, High Tolerance (Central-Top)**
- `forwardSpeed`: 54-57, `waypointThreshold`: 0.108-0.113
- **Result**: Mixed outcomes - some finished laps with high error (orange/red circles)
- **Insight**: Higher speeds introduce sim-to-real discrepancies even when laps complete

**High Speed, Low Tolerance (Bottom-Right)**
- `forwardSpeed`: 66-70, `waypointThreshold`: 0.085-0.093
- **Result**: Mixed outcomes with many unfinished laps (red squares) and high error
- **Insight**: Aggressive parameter combinations lead to both failure and high gap

**Critical Finding**: Finished laps (green circles) can still exhibit high sim-to-real gap (orange/red coloring), indicating that **lap completion does not guarantee simulation accuracy**.

#### 3. Turn Speed vs. Tolerance Analysis

**Key Observations:**

**Low Turn Speed Regions (20-24)**
- **Result**: High concentration of unfinished laps (red squares) with high error
- **Insight**: Insufficient turn speed prevents successful navigation, especially with lower tolerance

**Optimal Turn Speed Clusters:**
- `turnSpeed`: 27-29, `tolerance`: 0.080-0.084 → Low error, finished laps
- `turnSpeed`: 28-30, `tolerance`: 0.092-0.095 → Low error, finished laps
- `turnSpeed`: 34-36, `tolerance`: 0.098-0.102 → Low error, finished laps
- `turnSpeed`: 36-39, `tolerance`: 0.104-0.110 → Low error, finished laps
- `turnSpeed`: 24-26, `tolerance`: 0.116-0.120 → Low error, finished laps

**Insight**: Multiple "sweet spots" exist where turn speed and tolerance balance well, but they require careful parameter tuning.

**High Error Regions:**
- Bottom-left clusters (`turnSpeed`: 20-24, `tolerance`: 0.088-0.105) show mix of finished/unfinished with high error
- **Insight**: Low turn speed combined with mid-range tolerance creates unstable behavior with high sim-to-real gap

#### 4. Forward Speed vs. Turn Speed Analysis

**Key Observations:**

**Successful Parameter Combinations:**
- High `turnSpeed` (37.5-40) + Low `forwardSpeed` (30-35) → Finished laps, low error
- Mid `turnSpeed` (35-37.5) + Mid `forwardSpeed` (40-45) → Finished laps, low error
- Lower `turnSpeed` (25-28) + Mid `forwardSpeed` (35-42) → Finished laps, low error
- Mid `turnSpeed` (35-36) + Higher `forwardSpeed` (52-58) → Finished laps, low error
- Lower `turnSpeed` (22.5-23.5) + Higher `forwardSpeed` (62-68) → Finished laps, low error

**Problematic Regions:**
- Dense cluster: `forwardSpeed`: 54-58, `turnSpeed`: 20-22.5
  - **Result**: Many unfinished laps (red squares) with high error (orange to red)
  - **Insight**: High forward speed with low turn speed creates instability

- High speed region: `forwardSpeed`: 65-70, `turnSpeed`: 33-34
  - **Result**: Unfinished laps with high error
  - **Insight**: Very high speeds require precise turn speed matching

**Critical Finding**: The relationship between forward and turn speed is **non-linear** - successful combinations form multiple distinct clusters rather than a continuous region.

#### 5. 3D Parameter Space Analysis

**Spatial Distribution:**
- Samples are **not uniformly distributed** - MAB sampler successfully focused exploration on high-error regions
- Clusters form in specific 3D regions, indicating parameter interactions

**High Gap Clusters:**
- Concentrated in regions with:
  - High `forwardSpeed` (60-70) + Low `turnSpeed` (20-25) + Mid `tolerance` (0.085-0.105)
  - Mid `forwardSpeed` (50-60) + Low `turnSpeed` (20-24) + Low `tolerance` (0.080-0.090)

**Low Gap Clusters:**
- Multiple successful regions scattered throughout space:
  - Low speed regions (forwardSpeed 30-45) with various turn speeds
  - Mid-to-high turn speeds (28-40) with moderate forward speeds
  - Higher tolerance values (0.105-0.120) provide more robustness

**Key Insight**: The parameter space has **multiple disconnected regions** of low gap, suggesting that successful configurations are not simply "moderate values" but require specific combinations.

### Critical Insights

#### 1. Lap Completion ≠ Low Gap

**Finding**: Many finished laps (green circles) exhibit high sim-to-real gap (orange/red coloring).

**Implication**: 
- Successfully completing a lap in both sim and hardware doesn't guarantee they follow the same trajectory
- The gap metric captures trajectory differences even when both runs complete the task
- This validates the need for multi-metric analysis (waypoint, boundary, trajectory)

#### 2. Parameter Interactions Are Complex

**Finding**: Successful regions form disconnected clusters, not continuous regions.

**Implication**:
- Simple parameter tuning (adjusting one parameter at a time) may miss optimal combinations
- MAB sampler's multi-dimensional exploration is essential
- Parameter interactions create non-linear response surfaces

#### 3. Speed-Tolerance Trade-offs

**Finding**: 
- Low speed + high tolerance → reliable, low gap
- High speed + low tolerance → high gap, frequent failures
- Mid-range combinations show mixed results

**Implication**:
- Conservative parameters (low speed, high tolerance) provide robustness
- Aggressive parameters (high speed, low tolerance) increase both failure rate and sim-to-real gap
- Optimal performance requires balancing all three parameters simultaneously

#### 4. Turn Speed Critical for Stability

**Finding**: Low turn speeds (20-24) consistently lead to high error and unfinished laps.

**Implication**:
- Turn speed must be sufficient for waypoint navigation
- Insufficient turn speed cannot be compensated by adjusting other parameters
- Minimum turn speed threshold exists (~25-27) for reliable performance

#### 5. MAB Sampler Effectiveness

**Finding**: Sample distribution shows clustering in high-error regions.

**Implication**:
- MAB sampler successfully identified and explored problematic parameter regions
- Exploration-exploitation balance worked - both high and low gap regions sampled
- 30% high-gap samples indicate effective identification of problem areas

### Recommendations

#### For Simulation Fidelity:
1. **Focus on high-gap regions** (30 samples) to identify simulation model limitations
2. **Investigate why high-speed, low-turn-speed combinations** show high gap even when laps complete
3. **Analyze trajectory differences** in finished-lap, high-gap cases to understand divergence

#### For Hardware Control:
1. **Prefer conservative parameters** (low speed, high tolerance) for reliable operation
2. **Avoid high-speed, low-turn-speed combinations** - they lead to both failure and high gap
3. **Use identified optimal clusters** as starting points for further tuning

#### For Future Sampling:
1. **Increase exploration** in boundary regions between high/low gap clusters
2. **Fine-tune** around identified low-gap clusters to find optimal configurations
3. **Investigate** why some finished-lap samples have high gap - may reveal systematic simulation errors

### Statistical Summary

- **Total Samples**: 100
- **Finished Laps**: Majority (exact count varies by visualization)
- **High Gap (≥0.60)**: 30 samples (30%)
- **Low Gap (<0.60)**: 70 samples (70%)
- **Gap Range**: [0.065, 1.000]
- **Best Observed Gap**: 0.065 (excellent sim-to-real alignment)
- **Worst Observed Gap**: 1.000 (complete divergence)

### Visualization Files

The results are visualized in four complementary views:
1. **3D Parameter Space**: Complete 3D view of all parameters and gap values
2. **Forward Speed vs. Tolerance**: 2D projection showing speed-tolerance relationships
3. **Turn Speed vs. Tolerance**: 2D projection showing turn-tolerance relationships  
4. **Forward Speed vs. Turn Speed**: 2D projection showing speed-speed relationships

Each visualization uses:
- **Green circles**: Finished laps (True)
- **Red squares**: Unfinished laps (False)
- **Color gradient**: Combined error (green = low gap, red = high gap)

---

## Part 10: Troubleshooting

### Common Issues

**1. Robot Not Moving in Simulation**
- Check `webotsSupervisor` is set on robot object
- Verify Emitter/Receiver channels match (default: 1)
- Check robot controller receives messages
- Verify motors enabled in controller

**2. Robot Not Moving in Hardware**
- Check BLE connection status
- Verify mocap target ID matches robot
- Check motor command format (deg/s)
- Verify robot firmware is running

**3. Mocap Position Not Updating**
- Check NatNet connection (server/client IPs)
- Verify target ID in mocap system
- Check coordinate system conversion
- Verify `updatePositionFromMocap()` called each step

**4. Gap Metrics Always Zero**
- Check log files exist and are readable
- Verify log format matches `LogDecoder` expectations
- Check waypoint definitions match behavior
- Verify trajectory alignment parameters

**5. Sampler Not Converging**
- Increase exploration ratio for more exploration
- Check parameter domain ranges are reasonable
- Verify error values are in [0, 1] range
- Check bucket count (too few = coarse, too many = slow)

---

## Summary

This system provides a complete framework for evaluating sim-to-real gap in robotic systems:

1. **Robotics Domain**: Simulator-agnostic behaviors and actions
2. **Webots Integration**: Precise digital twin with millimeter accuracy
3. **Hardware Integration**: BLE control and mocap feedback
4. **Gap Analysis**: Multi-metric comparison (waypoint, boundary, trajectory)
5. **Intelligent Sampling**: MAB-based parameter exploration
6. **Experimental Validation**: 100-sample study revealing critical parameter interactions

### Key Results

Analysis of 100 parameter samples revealed:
- **30% high-gap samples** (≥0.60) identifying problematic parameter regions
- **70% low-gap samples** (<0.60) showing good sim-to-real alignment
- **Complex parameter interactions** with disconnected optimal regions
- **Critical finding**: Lap completion does not guarantee low sim-to-real gap
- **Multiple optimal clusters** requiring careful multi-dimensional tuning

The architecture enables systematic identification of parameter regions where simulation and reality diverge, providing insights for improving both simulation fidelity and hardware control. The experimental results demonstrate the effectiveness of the MAB sampling strategy in exploring the parameter space and identifying regions of high discrepancy.

