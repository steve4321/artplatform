"""
Blender background script: project a concept image onto a UV-mapped mesh.

Uses front-facing camera to render the concept image, then maps it to
the UV texture by rasterizing triangles from the front camera view.

Usage:
    blender --background --python texture_projection.py -- <input.glb> <concept_image.png> <output_dir>

Stdout (single JSON line on success):
    {"albedo_path": "...", "output_path": "...", "resolution": 2048}
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


def _setup_front_camera(mesh_obj):
    import bpy
    import mathutils

    bbox = mesh_obj.bound_box
    xs = [v[0] for v in bbox]
    ys = [v[1] for v in bbox]
    zs = [v[2] for v in bbox]

    cx = (min(xs) + max(xs)) / 2
    cy = min(ys)
    cz = (min(zs) + max(zs)) / 2

    mesh_width = max(xs) - min(xs)
    mesh_height = max(zs) - min(zs)
    max_dim = max(mesh_width, mesh_height, 0.1)

    cam_data = bpy.data.cameras.new("ProjCam")
    cam_obj = bpy.data.objects.new("ProjCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    cam_dist = max_dim * 2.0
    cam_obj.location = (cx, cy - cam_dist, cz)
    direction = mathutils.Vector((cx, cy, cz)) - cam_obj.location
    rot_quat = direction.normalized().to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()

    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max_dim * 1.3

    bpy.context.scene.camera = cam_obj
    return cam_obj


def _render_front_view(mesh_obj, resolution, output_dir):
    import bpy

    mat = bpy.data.materials.new(name="SolidWhite")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (1, 1, 1, 1)
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(emit.outputs["Emission"], output.inputs["Surface"])

    if len(mesh_obj.data.materials) == 0:
        mesh_obj.data.materials.append(mat)
    else:
        mesh_obj.data.materials[0] = mat

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.filepath = os.path.join(output_dir, "render_front.png")
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    bpy.context.scene.world = None

    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    scene.camera.select_set(True)
    bpy.context.view_layer.objects.active = scene.camera

    bpy.ops.render.render(write_still=True)

    return scene.render.filepath


def _project_texture(mesh_obj, concept_image_path, resolution, output_dir):
    import bpy
    import mathutils
    import numpy as np
    from PIL import Image

    cam_obj = _setup_front_camera(mesh_obj)

    bbox = mesh_obj.bound_box
    xs = [v[0] for v in bbox]
    ys = [v[1] for v in bbox]
    zs = [v[2] for v in bbox]
    cx = (min(xs) + max(xs)) / 2
    cy = min(ys)
    cz = (min(zs) + max(zs)) / 2
    max_dim = max(max(xs) - min(xs), max(zs) - min(zs), 0.1)

    cam = cam_obj.data
    ortho_half = cam.ortho_scale / 2
    aspect = resolution / resolution

    concept_img = np.array(Image.open(concept_image_path).convert("RGB").resize((resolution, resolution)))
    albedo = np.full((resolution, resolution, 3), 128, dtype=np.uint8)

    mesh = mesh_obj.data
    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        _print_error("No UV layer on mesh")

    world_matrix = mesh_obj.matrix_world
    cam_matrix = cam_obj.matrix_world.inverted()

    for poly in mesh.polygons:
        loop_indices = list(poly.loop_indices)
        for i in range(1, len(loop_indices) - 1):
            tri = (loop_indices[0], loop_indices[i], loop_indices[i + 1])
            _rasterize_tri(
                mesh, uv_layer, world_matrix, cam_matrix,
                cam_obj.location, cam, resolution,
                cx, cy, cz, max_dim,
                concept_img, albedo, tri,
            )

    for obj in list(bpy.data.objects):
        if obj.type == "CAMERA":
            bpy.data.objects.remove(obj, do_unlink=True)

    albedo_path = os.path.join(output_dir, "albedo.png")
    Image.fromarray(albedo, "RGB").save(albedo_path, "PNG")
    return albedo_path


def _rasterize_tri(mesh, uv_layer, world_matrix, cam_matrix_inv,
                   cam_loc, cam, res, cx, cy, cz, max_dim,
                   src_img, dst_img, tri_loops):
    import numpy as np

    screen_coords = []
    uv_coords = []
    for li in tri_loops:
        vi = mesh.loops[li].vertex_index
        local_co = mesh.vertices[vi].co
        world_co = world_matrix @ local_co

        dx = world_co.x - cx
        dz = world_co.z - cz
        ortho_half = cam.ortho_scale / 2
        sx = int((dx / ortho_half + 1) / 2 * res)
        sy = int((1 - (dz / ortho_half + 1) / 2) * res)
        sx = max(0, min(res - 1, sx))
        sy = max(0, min(res - 1, sy))
        screen_coords.append((sx, sy))

        uv = uv_layer.data[li].uv
        uv_coords.append((uv.x, uv.y))

    uv_a, uv_b, uv_c = uv_coords
    sc_a, sc_b, sc_c = screen_coords

    min_u = max(0, int(min(uv_a[0], uv_b[0], uv_c[0]) * res))
    max_u = min(res, int(max(uv_a[0], uv_b[0], uv_c[0]) * res) + 1)
    min_v = max(0, int(min(uv_a[1], uv_b[1], uv_c[1]) * res))
    max_v = min(res, int(max(uv_a[1], uv_b[1], uv_c[1]) * res) + 1)

    v0 = np.array(uv_b) - np.array(uv_a)
    v1 = np.array(uv_c) - np.array(uv_a)

    dot00 = v0 @ v0
    dot01 = v0 @ v1
    dot11 = v1 @ v1
    denom = dot00 * dot11 - dot01 * dot01
    if abs(denom) < 1e-10:
        return

    h, w = src_img.shape[:2]

    for py in range(min_v, max_v):
        for px in range(min_u, max_u):
            v2 = np.array([px / res, py / res]) - np.array(uv_a)
            dot02 = v0 @ v2
            dot12 = v1 @ v2
            u_bary = (dot11 * dot02 - dot01 * dot12) / denom
            v_bary = (dot00 * dot12 - dot01 * dot02) / denom
            w_bary = 1 - u_bary - v_bary

            if w_bary < -0.01 or u_bary < -0.01 or v_bary < -0.01:
                continue

            src_x = int(w_bary * sc_a[0] + u_bary * sc_b[0] + v_bary * sc_c[0])
            src_y = int(w_bary * sc_a[1] + u_bary * sc_b[1] + v_bary * sc_c[1])

            if 0 <= src_x < w and 0 <= src_y < h:
                dst_img[py, px] = src_img[src_y, src_x]


def _apply_baked_texture(mesh_obj, albedo_path: str) -> None:
    import bpy

    mat = bpy.data.materials.new(name="FinalMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    albedo_img = bpy.data.images.load(albedo_path)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = albedo_img

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

    albedo_path = _project_texture(mesh_obj, concept_image_path, resolution, output_dir)

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
