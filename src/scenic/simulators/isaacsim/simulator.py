from scenic.core.simulators import Simulation, Simulator
from isaacsim import SimulationApp
from scenic.core.vectors import Vector
from scenic.core.simulators import SimulationCreationError
import scenic.simulators.isaacsim.utils.utils as utils
from scenic.core.regions import MeshVolumeRegion
import math
import asyncio
import tempfile
from os import path
import trimesh

class IsaacSimSimulator(Simulator):

    def __init__(self, environmentUSDPath=None):
        super().__init__()
        self.client = SimulationApp({"headless": False})
        self.environmentUSDPath = environmentUSDPath
        from isaacsim.core.api import World
        timestep = 1.0/60.0 #if timestep is None else timestep
        self.world = World(stage_units_in_meters=1.0, physics_dt=timestep, rendering_dt=timestep)

    def createSimulation(self, scene, **kwargs):
        return IsaacSimSimulation(
            scene,
            self.client,
            self.world,
            self.environmentUSDPath,
            **kwargs
        )
    
    def destroy(self):
        self.client.close()

class IsaacSimSimulation(Simulation):

    def __init__(self, scene, client, world, environmentUSDPath, *, timestep, **kwargs):

        from isaacsim.core.utils.extensions import enable_extension
        enable_extension("omni.kit.asset_converter")

        self.client = client
        self.environmentUSDPath = environmentUSDPath
        timestep = 1.0/60.0 if timestep is None else timestep
        self.world = world
        self.tmpMeshDir = tempfile.mkdtemp()
        super().__init__(scene, timestep=timestep, **kwargs)

    def setup(self):
        import omni.kit.actions.core
        import isaacsim.core.utils.stage as stage_utils
        super().setup()
        action_registry = omni.kit.actions.core.get_action_registry()
        action = action_registry.get_action("omni.kit.viewport.menubar.lighting", "set_lighting_mode_camera")
        if self.environmentUSDPath:
            stage_utils.add_reference_to_stage(path.abspath(self.environmentUSDPath), f"/World/environment") 
        action.execute()
        self.world.play()

    def step(self):
        self.world.step()

    def createObjectInSimulator(self, obj):
        
        isaac_sim_obj = None

        if obj.blueprint == "IsaacSimPreexisting":
            return

        # object without usd
        if obj.blueprint == "IsaacSimObject" and not obj.usd_path:
            objectScaledMesh = MeshVolumeRegion(
                mesh=obj.shape.mesh,
                dimensions=(obj.width, obj.length, obj.height),
            ).mesh
            obj_file_path = path.join(self.tmpMeshDir, f"{obj.name}.obj")
            usd_file_path = path.join(self.tmpMeshDir, f"{obj.name}.usd")
            trimesh.exchange.export.export_mesh(objectScaledMesh, obj_file_path)
            asyncio.get_event_loop().run_until_complete(utils.convert(obj_file_path, usd_file_path, True))
            obj.usd_path = usd_file_path

        isaac_sim_obj = obj.create()

        if obj.blueprint == "IsaacSimEnvironment":
            return

        try:
            self.world.scene.add(isaac_sim_obj)
        except:
            raise SimulationCreationError(f"Unable to add {obj.name} to world")
        
        # if it is a robot we need to reset the world
        if obj.blueprint == 'Robot':
            self.world.reset()

        # specific for franka robot post setup
        if obj.blueprint == "Franka":
            self.world.reset()
            obj.setup_post_load(self.world)

    def getProperties(self, obj, properties):
        from isaacsim.core.utils.rotations import quat_to_euler_angles

        if not obj.physics:  # static object 
            return {prop: getattr(obj, prop) for prop in properties}

        isaacObj = self.world.scene.get_object(obj.name)
        position, orientation = isaacObj.get_world_pose()
        x, y, z = position
        yaw, pitch, roll = quat_to_euler_angles(orientation)
        lx, ly, lz = isaacObj.get_linear_velocity()
        ax, ay, az = isaacObj.get_angular_velocity()
        speed = math.hypot(lx, ly, lz)
        angularSpeed = math.hypot(ax, ay, az)

        values = dict(
            position=Vector(x, y, z),
            velocity=Vector(lx, ly, lz),
            speed=speed,
            angularSpeed=angularSpeed,
            angularVelocity=Vector(ax, ay, az),
            yaw=yaw,
            pitch=pitch,
            roll=roll,
        )
        return values
    
    def destroy(self):
        self.world.stop()
        self.world.clear()
        self.world.reset()