from scenic.simulators.isaacsim.behaviors import *
from scenic.simulators.isaacsim.utils.utils import getPreexistingObj
import trimesh

param environmentUSDPath = localPath("../../../assets/usd/simple_room_flattened.usd")
param environmentMeshPath = localPath("../../../assets/meshes_converted/simple_room_flattened_usd.gltf")
param environmentInfoPath = localPath("./simple_room_flattened_info.json")
param numToys = 10

model scenic.simulators.isaacsim.model

floor = getPreexistingObj("/Root/Towel_Room01_floor_bottom_218/Towel_Room01_floor_bottom")
table = getPreexistingObj('/Root/table_low_327/table_low')
small_bin_mesh = repairMesh(trimesh.load(localPath("../../../assets/meshes_converted/small_KLT_usd.obj")).to_geometry())

small_bin = new IsaacSimObject with usd_path "C:/isaacsim_assets/Assets/Isaac/4.5/Isaac/Props/KLT_Bin/small_KLT.usd",
    with shape MeshShape(small_bin_mesh),
    on table, 
    at (Range(-.5, .5), Range(-.5, .5)),
    with color (.78, .08, 0.52)

cube = new IsaacSimObject on table, 
    at (Range(-.5, .5), Range(-.5, .5)),
    with width .0515, 
    with height .0515, 
    with length .0515, 
    with color (1, 0, 0), 
    with shape BoxShape(),
    with mass .05,

new Franka on table, at (0, 0), 
    with behavior PickAndPlace(cube, (small_bin.x, small_bin.y, small_bin.z + .2)),
    with color (1, 1, 1)