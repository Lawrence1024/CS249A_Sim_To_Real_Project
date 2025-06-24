# Copyright (c) 2020-2024, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import argparse
import asyncio
import os
import tempfile
import trimesh
from pathlib import Path
import json
import numpy as np

from scenic.core.utils import repairMesh
from isaacsim import SimulationApp

async def convert(in_file, out_file, load_materials=False):
    # This import causes conflicts when global
    import omni.kit.asset_converter

    def progress_callback(progress, total_steps):
        pass

    converter_context = omni.kit.asset_converter.AssetConverterContext()
    # setup converter and flags
    converter_context.ignore_materials = not load_materials
    converter_context.ignore_animation = False
    converter_context.ignore_cameras = True
    # converter_context.single_mesh = True
    # converter_context.smooth_normals = True
    # converter_context.preview_surface = False
    # converter_context.support_point_instancer = False
    # converter_context.embed_mdl_in_usd = False
    converter_context.use_meter_as_world_unit = True
    converter_context.create_world_as_default_root_prim = True
    instance = omni.kit.asset_converter.get_instance()
    task = instance.create_converter_task(in_file, out_file, progress_callback, converter_context)
    success = True
    while True:
        success = await task.wait_until_finished()
        if not success:
            await asyncio.sleep(0.1)
        else:
            break
    return success

# Remove the ground plane (NOT be done in environment files)
def remove_ground_plane(file_path, output_path):
    stage = Usd.Stage.Open(file_path)

    for prim in stage.Traverse():
        if "groundplane" in str(prim.GetPath()).lower():
            prim.SetActive(False)

    stage.GetRootLayer().Export(output_path)

# Repair the mesh so that it is compatible as a Scenic Mesh
# This is doesnt seem to do anything - I still have to repair in Scenic when its loaded
def fix_mesh(model_path):
    mesh = trimesh.load(model_path)
    # if it is a scene, we need to combine individual geometry
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.to_geometry()
    # repair the mesh 
    mesh = repairMesh(mesh)
    mesh.export(model_path)

def compute_bbox(prim):
    """
    Compute Bounding Box using ComputeWorldBound at UsdGeom.Imageable
    See https://openusd.org/release/api/class_usd_geom_imageable.html

    Args:
        prim: A prim to compute the bounding box.
    Returns: 
        A range (i.e. bounding box), see more at: https://openusd.org/release/api/class_gf_range3d.html
    """
    from pxr import UsdGeom
    imageable = UsdGeom.Imageable(prim)
    time = Usd.TimeCode.Default()
    bound = imageable.ComputeWorldBound(time, UsdGeom.Tokens.default_)
    bound_range = bound.ComputeAlignedBox()
    return bound_range


def decompose_matrix(mat):
    from pxr import Gf
    reversed_ident_mtx = reversed(Gf.Matrix3d())

    translate = mat.ExtractTranslation()
    scale = Gf.Vec3d(*(v.GetLength() for v in mat.ExtractRotationMatrix()))
    mat.Orthonormalize()
    rotate = Gf.Vec3d(*reversed(mat.ExtractRotation().Decompose(*reversed_ident_mtx)))
    return translate, rotate, scale


def get_mesh_info(usd_path, output_path, folder):
    from pxr import UsdGeom
    import omni
    from isaacsim.core.utils.stage import open_stage
    
    transforms = {}
    open_stage(usd_path)
    usd_context = omni.usd.get_context()
    stage = usd_context.get_stage()

    mesh_prim_paths = [
        (prim, prim.GetPath()) for prim in stage.Traverse()
        if prim.IsA(UsdGeom.Mesh) and prim.IsValid()
    ]

    count = 0 
    for prim, prim_path in mesh_prim_paths:
        new_name = f"prim_{count}"
        parent_path = prim_path.GetParentPath()
        new_path = parent_path.AppendChild(new_name)

        bbox = compute_bbox(prim)
        pos = (bbox.min + bbox.max) * .5

        xformable = UsdGeom.Xformable(prim)
        matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        _, rot, _ = decompose_matrix(matrix)

        # Move the prim
        omni.kit.commands.execute(
            "MovePrim",
            path_from=str(prim_path),
            path_to=str(new_path)
        )

        transforms[new_name] = {}
        transforms[new_name]['full_path'] = str(prim_path)
        transforms[new_name]['orientation'] = np.array(rot).tolist()
        transforms[new_name]['position'] = np.array(pos).tolist()

        omni.usd.get_context().save_as_stage(output_path)
        out_file = folder + "_converted/" + Path(usd_path).stem + "_info.json"

        count += 1

    with open(out_file, 'w') as f:
        json.dump(transforms, f, indent=2)

    print(f"---Added {out_file}")

def asset_convert(args):
    for folder in args.folders:
        local_asset_output = folder + "_converted"
        omni.client.create_folder(f"{local_asset_output}")
    
    tmpDir = tempfile.mkdtemp()
    for folder in args.folders:
        print(f"\nConverting folder {folder}...")

        _, models = omni.client.list(folder)
        for i, entry in enumerate(models):
            if i >= args.max_models:
                print(f"max models ({args.max_models}) reached, exiting conversion")
                break

            model = str(entry.relative_path)
            model_name = os.path.splitext(model)[0]
            model_format = (os.path.splitext(model)[1])[1:]
            # Supported input file formats
            if model_format == "usd":
                input_model_path = folder + "/" + model

                # rename the child meshes before conversion 
                if model in args.environments:
                    renamed_usd = os.path.join(tmpDir, f"{model}.usd") 
                    get_mesh_info(input_model_path, renamed_usd, folder)
                    input_model_path = renamed_usd
                # if it is not environment, remove the ground plane
                else:
                    usd_without_ground = os.path.join(tmpDir, f"{model}.usd") 
                    remove_ground_plane(input_model_path, usd_without_ground)
                    input_model_path = usd_without_ground
                
                converted_model_path = folder + "_converted/" + model_name + "_" + model_format + ".gltf"
                
                if not os.path.exists(converted_model_path):
                    status = asyncio.get_event_loop().run_until_complete(
                        convert(input_model_path, converted_model_path, True)
                    )
                    if not status:
                        print(f"ERROR Status is {status}")

                    # if its not an environment, we should just repair the mesh now
                    # fill gaps and voxelize for Scenic
                    # if model not in args.environments:
                    #     fix_mesh(converted_model_path)
                    print(f"---Added {converted_model_path}")

if __name__ == "__main__":
    kit = SimulationApp()

    import omni
    from isaacsim.core.utils.extensions import enable_extension
    from pxr import Usd 

    enable_extension("omni.kit.asset_converter")

    parser = argparse.ArgumentParser("Convert OBJ/STL assets to USD")
    parser.add_argument(
        "--folders", type=str, nargs="+", default=None, help="List of folders to convert (space seperated)."
    )
    parser.add_argument(
        "--max-models", type=int, default=50, help="If specified, convert up to `max-models` per folder."
    )
    parser.add_argument(
        "--load-materials", action="store_true", help="If specified, materials will be loaded from meshes"
    )

    parser.add_argument(
        "--environments", type=str, nargs="+", default=[],
        help="List of .usd filenames (not paths) to treat as environments. Others are treated as robots."
    )

    args, unknown_args = parser.parse_known_args()

    if args.folders is not None:
        # Ensure Omniverse Kit is launched via SimulationApp before asset_convert() is called
        asset_convert(args)
    else:
        print(f"No folders specified via --folders argument, exiting")

    # cleanup
    kit.close()