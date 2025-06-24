from scenic.simulators.isaacsim.behaviors import *
from scenic.simulators.isaacsim.utils.utils import getPreexistingObj
import trimesh

param environmentUSDPath = localPath("../../../assets/usd/simple_room_flattened.usd")
param environmentMeshPath = localPath("../../../assets/meshes_converted/simple_room_flattened_usd.gltf")
param environmentInfoPath = localPath("./simple_room_flattened_info.json")

model scenic.simulators.isaacsim.model