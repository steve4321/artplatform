"""
Blender background script: project a concept image onto a UV-mapped mesh.

Usage:
    blender --background --python texture_projection.py -- <input.glb> <concept_image.png> <output_dir>

Stdout (single JSON line on success):
    {"albedo_path": "...", "normal_path": "...", "resolution": 2048}
Stdout on failure:
    {"error": "..."}
"""
from __future__ import annotations

import json
import os
import sys
import traceback


def _print_result(data: dict) -> None:
    print(json.dumps(data), flush=True)


def _print_error(message: str) -> None:
    print(json.dumps({"error": message}), flush=True)
    sys.exit(1)


def _load_mesh(input_path: str):
    import bpy

    ext = os.path.splitext(input_path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=input_path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=input_path)
    elif ext in (".obj",):
        bpy.ops.wm.obj_import(filepath=input_path)
    else:
        _print_error(f"Unsupported input format: {ext}")

    mesh_obj = None
    for obj in bpy.context.selected_objects:
        if obj.type == "MESH":
            mesh_obj = obj
            break
    if mesh_obj is None:
        for obj in bpy.data.objects:
            if obj.type == "MESH":
                mesh_obj = obj
                break
    if mesh_obj is None:
        _print_error("No mesh object found after import")
    return mesh_obj


def _ensure_uvs(mesh_obj) -> None:
    import bpy

    mesh = mesh_obj.data
    if len(mesh.uv_layers) == 0:
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=1.0472, margin_method="SCALED", island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")


def _setup_camera_front(mesh_obj):
    import bpy
    import mathutils

    bbox = mesh_obj.bound_box
    xs = [v[0] for v in bbox]
    ys = [v[1] for v in bbox]
    zs = [v[2] for v in bbox]

    cx = (min(xs) + max(xs)) / 2
    cz = (min(zs) + max(zs)) / 2
    mesh_depth = max(ys) - min(ys)
    mesh_width = max(xs) - min(xs)
    mesh_height = max(zs) - min(zs)
    max_dim = max(mesh_width, mesh_height, 0.1)

    cam_data = bpy.data.cameras.new("ProjCam")
    cam_obj = bpy.data.objects.new("ProjCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    cam_dist = max_dim * 1.5
    cam_obj.location = (cx, min(ys) - mesh_depth - cam_dist, cz)
    direction = mathutils.Vector((cx, min(ys) - mesh_depth * 0.5, cz)) - cam_obj.location
    rot_quat = direction.normalized().to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()

    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max_dim * 1.3

    bpy.context.scene.camera = cam_obj
    return cam_obj


def _bake_projection(mesh_obj, concept_image_path: str, resolution: int) -> str:
    import bpy

    mat_name = "ProjBakeMat"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex_img = nodes.new("ShaderNodeTexImage")
    tex_img.image = bpy.data.images.load(concept_image_path)
    tex_img.interpolation = "Linear"
    tex_img.extension = "CLIP"

    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")

    window_vec = nodes.new("ShaderNodeVectorMath")
    window_vec.operation = "MULTIPLY"
    window_vec.inputs[1].default_value = (1.0, 1.0, 0.0)

    add_vec = nodes.new("ShaderNodeVectorMath")
    add_vec.operation = "ADD"
    add_vec.inputs[1].default_value = (0.0, 0.0, 0.0)

    nodes.new("ShaderNodeUVMap")

    window_x = nodes.new("ShaderNodeSeparateXYZ")
    window_y = nodes.new("ShaderNodeSeparateXYZ")

    links.new(tex_coord.outputs["Window"], window_vec.inputs[0])
    links.new(window_vec.outputs["Vector"], add_vec.inputs[0])

    links.new(tex_coord.outputs["Window"], window_x.inputs[0])
    links.new(tex_coord.outputs["Window"], window_y.inputs[0])

    combine = nodes.new("ShaderNodeCombineXYZ")
    links.new(window_x.outputs["X"], combine.inputs[0])
    invert_y = nodes.new("ShaderNodeMath")
    invert_y.operation = "SUBTRACT"
    invert_y.inputs[0].default_value = 1.0
    links.new(window_y.outputs["Y"], invert_y.inputs[1])
    links.new(invert_y.outputs[0], combine.inputs[1])

    links.new(combine.outputs["Vector"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], tex_img.inputs["Vector"])

    emit = nodes.new("ShaderNodeEmission")
    links.new(tex_img.outputs["Color"], emit.inputs["Color"])

    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(emit.outputs["Emission"], output.inputs["Surface"])

    if len(mesh_obj.data.materials) == 0:
        mesh_obj.data.materials.append(mat)
    else:
        mesh_obj.data.materials[0] = mat

    bake_image = bpy.data.images.new("BakedAlbedo", width=resolution, height=resolution, alpha=True)
    bake_image.generated_color = (0.0, 0.0, 0.0, 1.0)

    tex_img.image = bpy.data.images.load(concept_image_path)

    bake_target = nodes.new("ShaderNodeTexImage")
    bake_target.image = bake_image
    nodes.active = bake_target

    bpy.context.view_layer.objects.active = mesh_obj
    mesh_obj.select_set(True)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.bake_type = "EMIT"

    bpy.ops.object.bake(type="EMIT")

    albedo_path = os.path.join(os.path.dirname(bpy.data.filepath) or "/tmp", "baked_albedo.png")
    bake_image.filepath_raw = albedo_path
    bake_image.file_format = "PNG"
    bake_image.save()

    return albedo_path


def _bake_projection_simple(mesh_obj, concept_image_path: str, resolution: int, output_dir: str) -> str:
    import bpy

    mat_name = "ProjBakeMat"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    concept_img = bpy.data.images.load(concept_image_path)

    tex_img = nodes.new("ShaderNodeTexImage")
    tex_img.image = concept_img

    tex_coord = nodes.new("ShaderNodeTexCoord")

    emit = nodes.new("ShaderNodeEmission")
    links.new(tex_coord.outputs["Window"], tex_img.inputs["Vector"])
    links.new(tex_img.outputs["Color"], emit.inputs["Color"])

    output_node = nodes.new("ShaderNodeOutputMaterial")
    links.new(emit.outputs["Emission"], output_node.inputs["Surface"])

    if len(mesh_obj.data.materials) == 0:
        mesh_obj.data.materials.append(mat)
    else:
        mesh_obj.data.materials[0] = mat

    bake_image = bpy.data.images.new("BakedAlbedo", width=resolution, height=resolution)
    bake_image.generated_color = (0.5, 0.5, 0.5, 1.0)

    bake_target = nodes.new("ShaderNodeTexImage")
    bake_target.image = bake_image
    nodes.active = bake_target

    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = mesh_obj
    mesh_obj.select_set(True)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.bake_type = "EMIT"
    scene.render.bake.use_selected_to_active = False

    bpy.ops.object.bake(type="EMIT", use_clear=False)

    albedo_path = os.path.join(output_dir, "albedo.png")
    bake_image.filepath_raw = albedo_path
    bake_image.file_format = "PNG"
    bake_image.save()

    return albedo_path


def _apply_baked_texture(mesh_obj, albedo_path: str) -> None:
    import bpy

    mat_name = "FinalMaterial"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    albedo_img = bpy.data.images.load(albedo_path)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = albedo_img
    tex.interpolation = "Linear"

    uv_map = nodes.new("ShaderNodeUVMap")

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    output_node = nodes.new("ShaderNodeOutputMaterial")

    links.new(uv_map.outputs["UV"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], principled.inputs["Base Color"])
    links.new(principled.outputs["BSDF"], output_node.inputs["Surface"])

    if len(mesh_obj.data.materials) == 0:
        mesh_obj.data.materials.append(mat)
    else:
        mesh_obj.data.materials[0] = mat


def _export_glb(output_path: str, mesh_obj) -> None:
    import bpy

    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj

    bpy.ops.export_scene.gltf(
        filepath=output_path,
        use_selection=True,
        export_format="GLB",
    )


def main() -> None:
    import bpy

    argv = sys.argv
    try:
        sep_idx = argv.index("--")
        input_path = argv[sep_idx + 1]
        concept_image_path = argv[sep_idx + 2]
        output_dir = argv[sep_idx + 3]
    except (ValueError, IndexError):
        _print_error(f"Usage: blender --background --python {__file__} -- <input.glb> <concept.png> <output_dir>")

    if not os.path.isfile(input_path):
        _print_error(f"Input file not found: {input_path}")
    if not os.path.isfile(concept_image_path):
        _print_error(f"Concept image not found: {concept_image_path}")

    os.makedirs(output_dir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    mesh_obj = _load_mesh(input_path)
    _ensure_uvs(mesh_obj)

    resolution = 2048

    cam_obj = _setup_camera_front(mesh_obj)
    del cam_obj

    albedo_path = _bake_projection_simple(mesh_obj, concept_image_path, resolution, output_dir)

    for obj in list(bpy.data.objects):
        if obj.type == "CAMERA":
            bpy.data.objects.remove(obj, do_unlink=True)

    _apply_baked_texture(mesh_obj, albedo_path)

    output_path = os.path.join(output_dir, "textured_output.glb")
    _export_glb(output_path, mesh_obj)

    _print_result({
        "albedo_path": albedo_path,
        "output_path": output_path,
        "resolution": resolution,
    })


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc(file=sys.stderr)
        _print_error(traceback.format_exc())
