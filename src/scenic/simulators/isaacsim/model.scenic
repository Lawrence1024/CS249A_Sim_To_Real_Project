import uuid
import numpy as np
import os
import trimesh
import json
from scenic.simulators.isaacsim.behaviors import *
from scenic.simulators.isaacsim.utils.utils import scenicToIsaacSimOrientation
from scenic.core.utils import repairMesh
from trimesh.transformations import decompose_matrix

try:
    from scenic.simulators.isaacsim.simulator import IsaacSimSimulator    # for use in scenarios
    from scenic.simulators.isaacsim.actions import *
    from scenic.simulators.isaacsim.actions import _Robot, _WheeledRobot, _HolonomicRobot, _ManipulatorRobot
    from scenic.simulators.isaacsim.utils.utils import scenicToIsaacSimOrientation, _addPreexistingObj, isPlanar, planeToMesh
except ModuleNotFoundError:
    # for convenience when testing without the isaacsim package
    from scenic.core.simulators import SimulatorInterfaceWarning
    import warnings
    warnings.warn('the "isaacsim" package is not installed; '
                  'will not be able to run dynamic simulations',
                  SimulatorInterfaceWarning)

    def IsaacSimSimulator(*args, **kwargs):
        """Dummy simulator to allow compilation without the 'isaacsim' package.

        :meta private:
        """
        raise RuntimeError('the "isaacsim" package is required to run simulations '
                           'from this scenario')

    class _Robot: pass
    class _WheeledRobot: pass
    class _HolonomicRobot: pass

# -- global parameters ---------------

#param timestep = 1.0/60.0
param environmentUSDPath = None
param environmentInfoPath = None
param environmentMeshPath = None
environmentMeshPath = globalParameters.environmentMeshPath
environmentInfoPath = globalParameters.environmentInfoPath

# ---------- simulator creation ----------

simulator IsaacSimSimulator(environmentUSDPath=globalParameters.environmentUSDPath)

# ---------- base classes ----------

class IsaacSimObject:

    name: f"Object_{uuid.uuid4().hex[:8]}"
    physics: True
    mass: None
    density: None
    usd_path: None
    blueprint: "IsaacSimObject"

    def create(self):

        from isaacsim.core.utils import prims
        from isaacsim.core.prims import SingleGeometryPrim, SingleRigidPrim
        from isaacsim.core.api.materials import PreviewSurface
        from omni.physx.scripts import utils

        prim_path = f"/World/{self.name}"

        prim = prims.create_prim(prim_path=prim_path, usd_path=os.path.abspath(self.usd_path))

        if self.physics:
            utils.setRigidBody(prim, "convexDecomposition", False)

            obj = SingleRigidPrim(
                prim_path=prim_path, 
                name=self.name,
                position=self.position,
                orientation=scenicToIsaacSimOrientation(self.orientation),
                mass=self.mass,
                density=self.density,
                linear_velocity=self.velocity)
        
        else:
            obj = SingleGeometryPrim(
                prim_path=prim_path,
                name=self.name,
                position=self.position,
                orientation=scenicToIsaacSimOrientation(self.orientation),
                collision=True,
            )

        if self.color:
            material = PreviewSurface(prim_path=f"/World/material/{self.name}", color=np.array(self.color))
            obj.apply_visual_material(material)

        return obj

class IsaacSimPreexisting(IsaacSimObject):
    allowCollisions: True
    blueprint: "IsaacSimPreexisting"
    physics: False

def create_controller(forward_func, name): 
    from isaacsim.core.api.controllers import BaseController
    
    class Controller(BaseController):
        def __init__(self):
            super().__init__(name=name)
            
        def forward(self, command):
            return forward_func(command)
    
    return Controller

class IsaacSimRobot(IsaacSimObject, _Robot):

    controller: None
    control: None
    blueprint: "Robot"

    def move(self, sim, command):
        robot = sim.world.scene.get_object(self.name)
        robot.apply_action(self.controller.forward(command=command))

    def create(self):

        from isaacsim.core.api.robots import Robot
        from isaacsim.core.utils.stage import add_reference_to_stage

        if self.control:
            self.controller = create_controller(self.control, f'{self.name}_controller')()

        prim_path = f"/World/{self.name}"

        add_reference_to_stage(os.path.abspath(self.usd_path), prim_path)

        return Robot(
            prim_path=prim_path, 
            name=self.name,
            position=self.position,
            orientation=scenicToIsaacSimOrientation(self.orientation)
        )

class Franka(IsaacSimRobot, _ManipulatorRobot):

    blueprint: "Franka"
    shape: MeshShape(
            trimesh.load(localPath("../../../../assets/meshes_converted/franka_alt_fingers_flattened_usd.gltf")).to_geometry(), 
            initial_rotation=(0,90 deg,0))

    def move(self, sim, target_object, goal_position):
        current_joint_positions = self._franka.get_joint_positions()
        actions = self._controller.forward(
            picking_position=sim.world.scene.get_object(target_object.name).get_local_pose()[0],
            placing_position=goal_position,
            current_joint_positions=current_joint_positions,
            end_effector_offset=np.array([0, 0.005, 0])
        )
        self._franka.apply_action(actions)

    def create(self):
        from isaacsim.robot.manipulators import SingleManipulator
        from isaacsim.robot.manipulators.grippers import ParallelGripper
        from isaacsim.storage.native import get_assets_root_path
        from isaacsim.core.utils.stage import add_reference_to_stage

        assets_root_path = get_assets_root_path()
        asset_path = assets_root_path + "/Isaac/Robots/Franka/franka_alt_fingers.usd"
        prim_path = f"/World/{self.name}"

        add_reference_to_stage(usd_path=asset_path, prim_path=prim_path)

        gripper = ParallelGripper(
            end_effector_prim_path=f"{prim_path}/panda_rightfinger",
            joint_prim_names=["panda_finger_joint1", "panda_finger_joint2"],
            joint_opened_positions=np.array([0.05, 0.05]),
            joint_closed_positions=np.array([0.02, 0.02]),
            action_deltas=np.array([0.01, 0.01]),
        )

        return SingleManipulator(
                    prim_path=prim_path, 
                    name=self.name,
                    end_effector_prim_name="panda_rightfinger", 
                    gripper=gripper)

    def setup_post_load(self, world):
        from isaacsim.robot.manipulators.examples.franka.controllers import PickPlaceController

        self._franka = world.scene.get_object(self.name)

        self._controller = PickPlaceController(
            name="pick_place_controller",
            gripper=self._franka.gripper,
            robot_articulation=self._franka,
        )
        self._franka.gripper.set_joint_positions(self._franka.gripper.joint_opened_positions)

class Create3(IsaacSimRobot, _WheeledRobot):

    shape: CylinderShape()
    width: 0.335
    length: 0.335
    height: .1

    def move(self, sim, throttle=0, steering=0):
        wheeled_robot = sim.world.scene.get_object(self.name)
        wheeled_robot.apply_wheel_actions(self.controller.forward(command=[throttle, steering]))

    def create(self):
        from isaacsim.robot.wheeled_robots.controllers.differential_controller import DifferentialController
        from isaacsim.robot.wheeled_robots.robots import WheeledRobot
        from isaacsim.core.api.materials import PreviewSurface
        from isaacsim.storage.native import get_assets_root_path

        self.controller = DifferentialController(name="simple_control", wheel_radius=0.03, wheel_base=0.1125)

        assets_root_path = get_assets_root_path()
        if assets_root_path is None:
            carb.log_error("Could not find Isaac Sim assets folder")

        create3_asset_path = assets_root_path + "/Isaac/Robots/iRobot/create_3.usd"
        prim_path = f"/World/{self.name}"

        prim = WheeledRobot(
            prim_path=prim_path, 
            name=self.name,
            create_robot=True,
            orientation=scenicToIsaacSimOrientation(self.orientation, initial_rotation=[0, 0, 0]),
            position=self.position,
            usd_path=create3_asset_path,
            wheel_dof_names=["left_wheel_joint", "right_wheel_joint"])
        
        if self.color:
            material = PreviewSurface(
            prim_path=f"/World/material/{self.name}",  
            color=np.array(self.color) if self.color else None)

            prim.apply_visual_material(material)

        return prim

class Kaya(IsaacSimRobot, _HolonomicRobot):

    width: 0.2
    length: 0.2
    height: 0.2

    def move(self, sim, forward_speed=0, lateral_speed=0, yaw_speed=0):
        wheeled_robot = sim.world.scene.get_object(self.name)
        wheeled_robot.apply_wheel_actions(self.controller.forward(command=[forward_speed, lateral_speed, yaw_speed]))

    def create(self):
        from isaacsim.core.api.materials import PreviewSurface
        from isaacsim.robot.wheeled_robots.controllers.holonomic_controller import HolonomicController
        from isaacsim.robot.wheeled_robots.robots import WheeledRobot
        from isaacsim.robot.wheeled_robots.robots.holonomic_robot_usd_setup import HolonomicRobotUsdSetup
        from isaacsim.storage.native import get_assets_root_path

        assets_root_path = get_assets_root_path()
        if assets_root_path is None:
            carb.log_error("Could not find Isaac Sim assets folder")

        kaya_asset_path = assets_root_path + "/Isaac/Robots/Kaya/kaya.usd"
        prim_path = f"/World/{self.name}"

        prim = WheeledRobot(
            prim_path=prim_path,
            name=self.name,
            wheel_dof_names=["axle_0_joint", "axle_1_joint", "axle_2_joint"],
            create_robot=True,
            usd_path=kaya_asset_path,
            position=self.position,
            orientation=scenicToIsaacSimOrientation(self.orientation, initial_rotation=[np.pi/2, 0, 0]),
        )

        kaya_setup = HolonomicRobotUsdSetup(
            robot_prim_path=prim_path, 
            com_prim_path=f"/World/{self.name}/base_link/control_offset")

        (
            wheel_radius,
            wheel_positions,
            wheel_orientations,
            mecanum_angles,
            wheel_axis,
            up_axis,
        ) = kaya_setup.get_holonomic_controller_params()

        self.controller = HolonomicController(
            name="holonomic_controller",
            wheel_radius=wheel_radius,
            wheel_positions=wheel_positions,
            wheel_orientations=wheel_orientations,
            mecanum_angles=mecanum_angles,
            wheel_axis=wheel_axis,
            up_axis=up_axis,
        )

        if self.color:
            material = PreviewSurface(
            prim_path=f"/World/material/{self.name}",  
            color=np.array(self.color) if self.color else None)

            prim.apply_visual_material(material)

        return prim

class GroundPlane(IsaacSimObject):

    width: 5
    length: 5
    height: 0.01
    physics: False
    blueprint: "GroundPlane"

    def create(self):
        from isaacsim.core.api.objects import GroundPlane

        return GroundPlane(
            name=self.name,
            prim_path="/World/GroundPlane", 
            z_position=0, 
            color=np.array(self.color) if self.color else None,
            scale=[self.width, self.length, self.height]
        )

# ---------- body ----------
if globalParameters.environmentUSDPath:

    with open(environmentInfoPath, "r") as inFile:

        scene = trimesh.load(localPath(environmentMeshPath))
        meshData = json.load(inFile)

        for node_name in scene.graph.nodes_geometry:
            mesh = scene.geometry[node_name]

            world_transform = scene.graph.get(node_name, "World")[0]
            scale, shear, angles, tr, persp = decompose_matrix(world_transform)

            local_center = mesh.bounding_box.centroid
            pitch, roll, yaw = angles
            local_center_homogeneous = np.append(local_center, 1.0)
            world_center = np.dot(world_transform, local_center_homogeneous)[:3]
            path = meshData[node_name]['full_path']

            if isPlanar(mesh): 
                mesh = planeToMesh(mesh)

            # just scales by 1/100, this should be updated to check the units
            newObj = new IsaacSimPreexisting at world_center, 
                        with shape MeshShape(repairMesh(mesh.apply_scale(.01))), 
                        with name path,
                        facing (yaw, pitch, roll)

            _addPreexistingObj(newObj)