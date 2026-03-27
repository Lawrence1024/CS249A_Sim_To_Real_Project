model scenic.simulators.isaacsim.model
from scenic.simulators.isaacsim.actions import _WheeledRobot, applyWheeledController

behavior DriveStraight():
    for i in range(200):
        wait
    while True:
        take applyWheeledController(0.03, -0.001075)

class Pololu3Pi(IsaacSimRobot, _WheeledRobot):
    usd_path: localPath("../../assets/robots/pololu_3pi/usd_out/pololu_3pi/pololu_3pi.usd")
    width: 0.096
    length: 0.0912
    height: 0.035

    def move(self, sim, throttle=0, steering=0):
        robot = sim.world.scene.get_object(self.name)
        robot.apply_wheel_actions(self.controller.forward(command=[throttle, steering]))

    def create(self):
        from isaacsim.robot.wheeled_robots.robots import WheeledRobot
        from isaacsim.robot.wheeled_robots.controllers.differential_controller import DifferentialController
        from isaacsim.core.utils.stage import add_reference_to_stage
        from scenic.simulators.isaacsim.utils.utils import scenicToIsaacSimOrientation
        import os

        parent_prim = f"/World/{self.name}"
        articulation_root = f"{parent_prim}/base_link"

        add_reference_to_stage(os.path.abspath(self.usd_path), parent_prim)
        robot = WheeledRobot(
            prim_path=articulation_root,
            name=self.name,
            wheel_dof_names=["left_wheel_joint", "right_wheel_joint"],
            create_robot=False,
        )

        self.controller = DifferentialController(
            name=f"{self.name}_controller",
            wheel_radius=0.016,
            wheel_base=0.064
        )

        q = scenicToIsaacSimOrientation(self.orientation)
        robot.set_world_pose(position=self.position, orientation=q)
        robot.set_default_state(position=self.position, orientation=q)

        return robot

ground = new GroundPlane with color (0.8, 0.8, 0.8)

c1 = new IsaacSimObject at (-0.60, 0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c2 = new IsaacSimObject at (-0.60, -0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c3 = new IsaacSimObject at (-1.20, 0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c4 = new IsaacSimObject at (-1.20, -0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c5 = new IsaacSimObject at (-1.80, 0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c6 = new IsaacSimObject at (-1.80, -0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c7 = new IsaacSimObject at (-2.40, 0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c8 = new IsaacSimObject at (-2.40, -0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c9 = new IsaacSimObject at (-3.00, 0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c10 = new IsaacSimObject at (-3.00, -0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c11 = new IsaacSimObject at (-3.60, 0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

c12 = new IsaacSimObject at (-3.60, -0.18, 0.03),
    with shape ConeShape(),
    with width 0.03,
    with length 0.03,
    with height 0.04,
    with color (1, 0, 0),
    with physics False

ego = new Pololu3Pi at (0, 0, 0.03),
    facing (180 deg, 0 deg, 0),
    with behavior DriveStraight