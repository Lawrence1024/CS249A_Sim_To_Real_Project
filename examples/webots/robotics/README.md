# Webots Robotics Examples

This folder contains example Scenic scenarios for robotics using the robotics domain with Webots simulator integration.

## Quick Start

This folder uses a simplified structure with **one core world file** and multiple Scenic scenario files:

### Core Files

- **`pololu.scenic`**: Square racetrack example - robot follows a square track with inner and outer boundaries
- **`webots_data/worlds/pololu.wbt`**: World file with the drivable Pololu robot and racetrack visualization
- **`webots_data/controllers/scenic_supervisor/scenic_supervisor.py`**: Supervisor controller that runs Scenic
- **`webots_data/controllers/simple_robot_controller/simple_robot_controller.py`**: Robot controller that executes motor commands

## How to Run

### Option 1: Open in Webots GUI

1. Open Webots
2. Go to `File` → `Open World...`
3. Navigate to: `Scenic/examples/webots/robotics/webots_data/worlds/pololu.wbt`
4. Click the "Play" button (▶) or press `Ctrl+Shift+4`

The simulation will start automatically with Scenic controlling the robot!

### Option 2: Run from Command Line

```bash
# From the Scenic root directory
webots examples/webots/robotics/webots_data/worlds/pololu.wbt
```

## Viewing Console Output in Webots

**Where to see the debug output:**

Webots has a built-in **console window** where all Python print statements appear. To view it:

1. **Look for the "Console" tab** at the bottom of the Webots window
2. If you don't see it, go to `View` → `Console` or press `Ctrl+Alt+C`
3. The debug message `DEBUG: Robot spawned at position: ...` will appear here

**Alternative locations:**
- If you launched Webots from a terminal, output may also appear in that terminal
- Check Windows: `Tools` → `Text Output` for additional console windows

## What You'll See

- A **square racetrack** with red outer lines and blue inner lines
- The robot spawns at the top-left of the track and follows waypoints in a square pattern
- The robot will continuously loop around the track
- The console will show debug messages as the robot patrols between waypoints
- The simulation runs for 60 seconds

## Understanding the Setup

### The World File (`pololu.wbt`)

Defines:
- **Supervisor robot** with Scenic controller
- **POLOLU_ROBOT** with differential drive (left/right motors)
- **Ground plane** for the robot to move on
- **Race track visualization** with red outer lines and blue inner lines forming a square
- **Communication devices** (Emitter/Receiver) for Scenic to send motor commands

### The Scenario File (`pololu.scenic`)

Defines:
- **Workspace region** (4x4 meters)
- **Robot spawns** at a fixed starting position at top-left of track
- **SquareTrackBehavior** that makes the robot follow waypoints in a square pattern
- **Termination** after 60 seconds

The robot continuously loops around the square track defined by the waypoints!

Scenic uses the robotics domain to control the robot through generic actions, which are translated to Webots motor commands via the controller.

## Why We Simplified

Before: 3 world files (simple_robot.wbt, line_following.wbt, obstacle_avoidance.wbt)
After: 1 world file (pololu.wbt)

**Why?** All three examples used the exact same robot (Pololu differential drive). The only differences were:
- Sensors (none, IR, ultrasonic) - not needed for basic motor control
- Environment (empty, line, obstacles) - can be added as needed

Now you just need one `.wbt` file that defines the robot, and you can write many `.scenic` files that control it!

## Track Design

The square racetrack consists of:

- **Outer track (red)**: 4x4 meter square centered at origin
- **Inner track (blue)**: 2x2 meter square creating a track with boundaries
- **Waypoints**: Middle path follows waypoints at [(-1.5, 2), (2, 1.5), (1.5, -2), (-2, -1.5)]

The robot follows the waypoints in order, creating a continuous square loop. The track visualization helps you see where the robot should travel!

## Troubleshooting

**Can't find the console output?**
- Look for the "Console" tab at the bottom of Webots
- Or go to `View` → `Console`
- Check for Python errors in red text

**Robot doesn't move?**
- Check console output for errors
- Verify Scenic is installed in Webots' Python
- Make sure controllers are enabled in Webots

**Robot not following the track?**
- Check console for errors
- Make sure the robot spawn position is correct (top-left of track)
- Try adjusting the waypoint threshold (0.3m) in the behavior if the robot overshoots

**Simulation doesn't start?**
- Verify `customData` in pololu.wbt points to the correct .scenic file (line 31)
- Check supervisor controller is set correctly

## Extending the Example

To create your own scenarios:

1. Copy `pololu.scenic` to a new file (e.g., `my_scenario.scenic`)
2. Modify the behavior or add constraints as needed
3. Update `customData` in `pololu.wbt` (line 31) to point to your new `.scenic` file

You can use different behaviors from `scenic.domains.robotics.behaviors`:
- `SquareTrackBehavior()`: Follow a square track with waypoints
- `PatrolBehavior(waypoints)`: Patrol between custom waypoints
- `RandomWalkBehavior()`: Random forward and turning motions
- `LineFollowingBehavior()`: Follow a line using IR sensors
- `ObstacleAvoidanceBehavior()`: Avoid obstacles using sensors

The power of Scenic is that **you just describe what you want** - define waypoints, behaviors, and the robot will follow them!
