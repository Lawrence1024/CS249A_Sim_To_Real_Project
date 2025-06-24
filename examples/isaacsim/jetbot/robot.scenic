model scenic.simulators.isaacsim.model

# takes a command and returns an ArticulationAction
# https://docs.isaacsim.omniverse.nvidia.com/latest/core_api_tutorials/tutorial_core_adding_controller.html
def jetbot_control(command):

    from isaacsim.core.utils.types import ArticulationAction
    throttle, steering = command
    wheel_radius = .03 
    wheel_base=0.1125
    joint_indices = np.array([0, 1]) 

    joint_velocities = [0.0, 0.0]
    joint_velocities[0] = ((2 * throttle) - (steering * wheel_base)) / (2 * wheel_radius)
    joint_velocities[1] = ((2 * throttle) + (steering * wheel_base)) / (2 * wheel_radius)

    return ArticulationAction(joint_velocities=joint_velocities, joint_indices=joint_indices)

# Jetbot robot
class Jetbot(IsaacSimRobot):
    usd_path: localPath("../../../assets/usd/jetbot.usd")
    # change this to be the right asset...
    shape: MeshShape.fromFile(localPath("../../../assets/meshes_converted/create_3_usd.obj"))
    control: jetbot_control