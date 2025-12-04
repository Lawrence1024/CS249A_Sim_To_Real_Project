# src/scenic/hardware/pololu/simulator.py

import time
import asyncio
from typing import Any, Dict

from scenic.core.simulators import Simulator, Simulation
from scenic.core.vectors import Vector


class HardwareSimulation(Simulation):
    """Simulation where the real robot + mocap act as the simulator."""

    def __init__(
        self,
        scene,
        timestep: float,
        interface,
        maxSteps=None,
        name: str = "HardwareSimulation",
        verbosity: int = 0,
    ):
        # Set interface BEFORE calling super().__init__() because setup() is called during init
        self.interface = interface
        self.timestep = timestep
        # All args after scene are keyword-only in Simulation.__init__
        super().__init__(
            scene,
            timestep=timestep,
            maxSteps=maxSteps,
            name=name,
            verbosity=verbosity,
        )

    # ----- Minimal hooks required by Scenic ---------------------------------

    def setup(self):
        """Set up hardware simulation.
        
        Always needed: Sets hardware interface on simulation objects.
        Only for dummy mocap: Initializes mocap pose to match robot's starting position.
        Real mocap systems naturally report the robot's actual position.
        """
        # Call parent setup to create objects first
        super().setup()
        
        # Set hardware interface on all simulation objects that need it
        # This is ALWAYS needed for both real hardware and dummy mocap
        for obj in self.objects:
            if hasattr(obj, "setHardwareInterface"):
                obj.setHardwareInterface(self.interface)
                
                # Initialize mocap pose ONLY if using dummy mocap (for testing)
                # Real mocap systems (mocap/mocap_estimator.py) don't have set_pose()
                # and will naturally report the robot's actual position from the mocap system
                mocap_estimator = self.interface.mocap_estimator
                if hasattr(mocap_estimator, "set_pose"):
                    # This is a dummy mocap - initialize it to match Scenic's starting position
                    # so that dummy mocap values match where Scenic thinks the robot starts
                    pos = obj.position
                    if hasattr(pos, 'x'):
                        x, y, z = pos.x, pos.y, pos.z
                    else:
                        x, y, z = pos[0], pos[1], pos[2] if len(pos) > 2 else (pos[0], pos[1], 0.0)
                    heading = obj.heading if hasattr(obj, "heading") else 0.0
                    mocap_estimator.set_pose(x, y, z, yaw=heading)

    def createObjectInSimulator(self, obj):
        # Nothing to create in an external simulator; robot already exists.
        pass

    def actionsAreCompatible(self, agent, actions):
        # Let Scenic check usual things (preconditions etc.)
        return super().actionsAreCompatible(agent, actions)

    def executeActions(self, allActions):
        """Use default implementation so action.applyTo(...) runs.

        For the Pololu model, SetMotorAction.applyTo will ultimately call
        setLeftMotor / setRightMotor on the Scenic object and (via your model
        code) fill a pending motor command buffer.
        """
        super().executeActions(allActions)

    # ----- Hardware integration ---------------------------------------------

    def step(self):
        """One real-world timestep.

        Called once per Scenic step *after* executeActions.
        Here we actually send motor commands to hardware and wait.
        """
        # 1) Send any pending motor commands for objects that expose the method
        for agent in self.agents:
            if hasattr(agent, "getPendingMotorCommand"):
                cmd = agent.getPendingMotorCommand()
                if cmd:
                    left, right = cmd
                    try:
                        # No outer event loop here; safe to use asyncio.run
                        asyncio.run(
                            self.interface.send_wheel_speed_command(left, right)
                        )
                    except Exception as e:
                        print(f"[HW] Error sending command: {e}")

        # 2) Sleep for one timestep to let the real world evolve
        time.sleep(self.timestep)

    def getProperties(self, obj, properties) -> Dict[str, Any]:
        """Return dynamic properties (position, heading, etc.) from mocap.

        Scenic calls this each step for each object whose properties are
        considered dynamic. For the Pololu robot we update from mocap;
        for everything else we just echo existing values.
        """
        vals: Dict[str, Any] = {}

        # If the object knows how to update itself from mocap, ask it to.
        if hasattr(obj, "updatePositionFromMocap"):
            try:
                obj.updatePositionFromMocap()
            except Exception as e:
                print(f"[HW] Mocap update error for {obj}: {e}")

        # After the call above, obj.position / obj.heading should be up to date.
        # We need to return ALL requested properties, so get them from the object
        for prop in properties:
            if hasattr(obj, prop):
                vals[prop] = getattr(obj, prop)
            else:
                # If property doesn't exist, provide a default based on common properties
                if prop == "position":
                    vals[prop] = getattr(obj, "position", Vector(0, 0, 0))
                elif prop == "heading":
                    vals[prop] = getattr(obj, "heading", 0.0)
                elif prop == "velocity":
                    vals[prop] = Vector(0, 0)
                elif prop == "speed":
                    vals[prop] = 0.0
                elif prop == "angularSpeed":
                    vals[prop] = 0.0
                else:
                    # For any other property, try to get it or use None
                    vals[prop] = getattr(obj, prop, None)

        return vals

    def destroy(self):
        """Clean up hardware at the end of the simulation."""
        try:
            asyncio.run(self.interface.send_wheel_speed_command(0, 0))
        except Exception:
            pass
        try:
            asyncio.run(self.interface.disconnect())
        except Exception:
            pass


class HardwareSimulator(Simulator):
    """Creates HardwareSimulation instances for a given HardwareInterface."""

    def __init__(self, interface, timestep: float = 0.02):
        super().__init__()
        self.interface = interface
        self.timestep = timestep

    def createSimulation(
        self,
        scene,
        *,
        timestep=None,
        maxSteps=None,
        verbosity: int = 0,
        name: str = "HardwareSimulation",
        **kwargs,
    ):
        # Use provided timestep or fall back to instance default
        if timestep is None:
            timestep = self.timestep
        return HardwareSimulation(
            scene=scene,
            timestep=timestep,
            interface=self.interface,
            maxSteps=maxSteps,
            name=name,
            verbosity=verbosity,
        )
