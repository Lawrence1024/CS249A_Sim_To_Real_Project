import asyncio
import scenic
from scenic.core.simulators import DummySimulator
from scenic.hardware.pololu.interface import HardwareInterface

SCENIC_FILE = "examples/webots/robotics/pololu_hardware.scenic"
TIMESTEP = 0.1  # 50 Hz
MAX_STEPS = 50  # or whatever duration you want


async def run_pololu_hardware():
    # ============================================================
    # Phase 1: Precompute Scenic actions with DummySimulator
    # ============================================================
    print("[Plan] Loading Scenic scenario and generating planning scene...")
    scenario = scenic.scenarioFromFile(SCENIC_FILE)

    # Scene used ONLY for planning (no hardware here)
    plan_scene, _ = scenario.generate()
    print("[Plan] Scene generated with", len(plan_scene.objects), "objects.")

    print("[Plan] Running DummySimulator to collect actions...")
    planner = DummySimulator()
    sim = planner.simulate(plan_scene, timestep=TIMESTEP, maxSteps=MAX_STEPS, name="pololu_plan")

    # sim.result.actions is a list; each element is a dict: {agent: (actions, ...)}
    action_sequence = sim.result.actions
    total_steps = len(action_sequence)
    print(f"[Plan] Collected actions for {total_steps} timesteps.")

    # ============================================================
    # Phase 2: Run on hardware by replaying actions
    # ============================================================
    print("[HW] Initializing HardwareInterface...")
    interface = HardwareInterface(mocap_target_id=15)  # or None for now
    if not await interface.connect():
        print("[HW] Failed to connect to BLE device; aborting.")
        return
    print("[HW] BLE connected.")

    print("[HW] Generating hardware scene...")
    hw_scene, _ = scenario.generate()  # fresh scene; contains HardwarePololuRobot
    robot = None
    for obj in hw_scene.objects:
        if hasattr(obj, "setHardwareInterface"):
            obj.setHardwareInterface(interface)
            robot = obj
            print("[HW] Attached HardwareInterface to:", obj)
            break

    if robot is None:
        print("[HW] ERROR: No HardwarePololuRobot found in hardware scene.")
        await interface.disconnect()
        return

    print("[HW] Starting action replay...")
    try:
        for step_idx, actions_at_t in enumerate(action_sequence):
            # actions_at_t: dict {agent_in_plan_scene: (action1, action2, ...)}
            # We only have one robot; just take all actions regardless of agent.
            all_actions = []
            for _, acts in actions_at_t.items():
                all_actions.extend(acts)

            # Apply each Scenic action to the *hardware* robot.
            # SetMotorAction.applyTo(agent, sim) usually just calls agent.setMotors(...)
            # and does not depend on 'sim', so we pass None.
            for act in all_actions:
                act.applyTo(robot, None)

            # After actions are applied, HardwarePololuRobot should have updated
            # its pending motor command via its setLeftMotor/setRightMotor hooks.
            cmd = None
            if hasattr(robot, "getPendingMotorCommand"):
                cmd = robot.getPendingMotorCommand()

            if cmd:
                left, right = cmd
                print(f"[HW] step {step_idx}: sending L={left}, R={right}")
                try:
                    await interface.send_wheel_speed_command(left, right)
                except Exception as e:
                    print(f"[HW] Error sending command at step {step_idx}: {e}")
            else:
                # No command this step; you can choose to send 0,0 or keep previous.
                print(f"[HW] step {step_idx}: no command, motors unchanged.")

            await asyncio.sleep(TIMESTEP)

        print("[HW] Finished replaying all actions.")

    except KeyboardInterrupt:
        print("\n[HW] KeyboardInterrupt; stopping early.")

    finally:
        print("[HW] Stopping robot and disconnecting...")
        try:
            await interface.send_wheel_speed_command(0, 0)
        except Exception:
            pass
        await interface.disconnect()
        print("[HW] Done.")


if __name__ == "__main__":
    asyncio.run(run_pololu_hardware())
