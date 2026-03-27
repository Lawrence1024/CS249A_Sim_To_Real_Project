# Webots ⇄ Scenic I/O Contract (What Webots Takes vs. What We Provide)

This document clarifies the boundary between Webots and our Scenic-based stack: what Webots expects/"takes" from us, what we must provide, and what flows back from Webots to Scenic.

## What Webots Takes (Inputs Webots Requires)

- World file (`.wbt`)
  - Defines the scene graph (ground, shapes/lines, markers), robots (`Robot` nodes), their physical properties, and controllers.
  - Each `Robot` node references a controller binary or Python script via `controller "..."`.
  - Communication devices per robot must be present if Scenic will command them:
    - `Emitter { channel N }`
    - `Receiver { channel N }`
  - Example: `DEF POLOLU_ROBOT` and `DEF POLOLU_ROBOT_2` are two physical robots existing in the world.

- Controller scripts available on disk
  - Webots loads controller code from the paths configured in the project; in our example:
    - Supervisor controller: `examples/webots/robotics/webots_data/controllers/scenic_supervisor/scenic_supervisor.py`
    - Robot controller: `examples/webots/robotics/webots_data/controllers/simple_robot_controller/simple_robot_controller.py`
  - Webots provides the Python API `from controller import Supervisor, Emitter, Receiver, RotationalMotor, ...` at runtime.

- `customData` on the supervisor
  - The `Supervisor` node’s `customData` holds the path to the Scenic scenario (relative or absolute). The supervisor controller resolves this path and loads the scenario.

- Motor interface expectations
  - Rotational motors receive angular velocity in rad/s via `RotationalMotor.setVelocity(value)`, clamped to ±`getMaxVelocity()`.
  - If we want the world to reflect realistic capabilities, we should set or respect `maxVelocity` in the `.wbt` (or query it from the device).

## What We Provide (Artifacts Our Stack Supplies)

- Scenic scenario (`.scenic`)
  - High-level intent and behaviors (e.g., `SquareTrackBehavior`, `PatrolBehavior`).
  - Bind Scenic objects to Webots nodes using `with webotsName "POLOLU_ROBOT"` so the Scenic runtime maps behaviors to actual robots.

- Scenic world model and simulator bindings
  - `scenic.simulators.webots.robotics_model` combines robotics domain classes with Webots specifics.
  - Actions from behaviors are turned into motor setpoints; our Webots model emits commands to the supervisor’s `Emitter`.

- Supervisor controller (Python)
  - Creates a `Supervisor`, sets up `Emitter`/`Receiver` (channel 1 by default), reads `customData`, and loads the Scenic scenario using `scenic.scenarioFromFile(path)`.
  - Loop: `scene, _ = scenario.generate()` → `simulate(scene)`.

- Robot controller (Python)
  - Each robot’s controller reads commands from its `Receiver` and drives motors via `RotationalMotor.setVelocity`.
  - Our current contract accepts motor commands as “percent” (0–100). The controller scales to rad/s using `getMaxVelocity()` and clamps to the device limit. If the command already appears to be in rad/s (very large magnitude), it is passed through but still clamped.

- Visualization assets (optional)
  - Track lines/waypoints are drawn in the `.wbt` using `IndexedLineSet` or primitive `Box` segments.
  - Waypoint markers (spheres) aid debugging.

## Data Flow Summary

1) Webots launches the world (`.wbt`).
2) Supervisor controller starts; loads Scenic scenario from `customData`.
3) Scenic compiles and samples the scene; behaviors emit actions.
4) Webots model in Scenic sends `motor_command` JSON over Supervisor `Emitter { channel 1 }` to robot(s).
5) Robot controller’s `Receiver { channel 1 }` decodes the command and applies `setVelocity` to left/right `RotationalMotor`.
6) Webots physics updates; supervision loop continues until the Scenic simulation finishes.

## Message Contract (Supervisor ↔ Robots)

- Motor command (JSON over Emitter/Receiver):
  ```json
  {
    "type": "motor_command",
    "left_speed": <number>,
    "right_speed": <number>
  }
  ```
  - Robot controller policy:
    - If `abs(value) ≤ 120`, treat as percent → rad/s via `value/100 * getMaxVelocity()`.
    - Else treat as rad/s. Always clamp to ±`getMaxVelocity()`.

- Waypoint notifications (optional):
  ```json
  {
    "type": "waypoint_reached",
    "waypoint_num": <number|string>
  }
  ```

## Responsibilities and Boundaries

- Webots is responsible for
  - Scene graph loading and simulation/physics.
  - Providing the runtime Python API (`controller` module).
  - Executing controllers and device drivers (motors, sensors, comms).

- Our Scenic setup is responsible for
  - Authoring `.scenic` scenarios and behaviors.
  - Providing the Webots-specific Scenic model which translates behaviors to commands.
  - Providing supervisor and robot controller scripts and ensuring devices (Emitter/Receiver, RotationalMotor) exist in the `.wbt`.

## Multi-Robot Deployment Contract

- For each Scenic robot you want to control, there must be a corresponding `Robot` node in the `.wbt`.
- Bindings are by name: `with webotsName "POLOLU_ROBOT_2"`.
- If robots should receive independent commands, assign distinct channels per robot (`Emitter/Receiver { channel N }`) and route messages accordingly in the supervisor.

## Units and Limits (Motors)

- Webots `RotationalMotor.setVelocity` uses rad/s.
- We send percent from Scenic; the robot controller maps to rad/s using `getMaxVelocity()`.
- Suggested `maxVelocity` for 3pi+ 2040 variants (approx.):
  - 15:1 HPCB (~1000 rpm) → ~105 rad/s
  - 30:1 HPCB (~600 rpm) → ~63 rad/s
  - 50:1 HPCB (~400 rpm) → ~42 rad/s
- Set these in the world file or accept the device default and let the controller scale to it.

## Minimum Checklist

- [.wbt] Supervisor with `customData` pointing to `.scenic` file.
- [.wbt] Each `Robot` has `Emitter`/`Receiver` and `RotationalMotor`s.
- [Controllers] `scenic_supervisor.py` and `simple_robot_controller.py` present.
- [Scenic] Scenario binds robots by `webotsName`; behaviors generate actions.
- [Scaling] Motor command contract (percent or rad/s) is implemented consistently.

---
This I/O contract ensures changes to scenarios, controllers, or the world file can be made independently while preserving a clear boundary between Webots runtime needs and our Scenic-layer responsibilities.


