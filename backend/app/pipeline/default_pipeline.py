DEFAULT_PIPELINE_STAGES: list[dict[str, str]] = [
    {"stage": "text_to_image", "processor": "sdxl"},
    {"stage": "image_to_3d", "processor": "triposr"},
    {"stage": "cleanup", "processor": "instant_meshes"},
    {"stage": "uv_material", "processor": "xatlas_bpy"},
    {"stage": "rig", "processor": "rigify"},
    {"stage": "animate", "processor": "hy_motion"},
]
