"""Pipeline stage registry — single source of truth for all pipeline definitions.

Canonical stage IDs:
  3D: text_to_image | image_to_3d | mesh_cleanup | uv_material | rigging | animation
  2D: text_to_image | post_process | format_output
"""
from __future__ import annotations

import os
import shutil

# Detect available backends
_HAS_BLENDER = bool(shutil.which("blender"))
_PROCESSOR_MODE = os.environ.get("PROCESSOR_MODE", "mock").lower()

# ── Stage definitions (canonical IDs across all modes) ──────────────────────

_STAGES_3D_COMMON = [
    {"stage": "text_to_image", "processor_name": "sdxl_mock"},
    {"stage": "image_to_3d", "processor_name": "triposr_mock"},
    {"stage": "mesh_cleanup", "processor_name": "instant_meshes_mock"},
    {"stage": "uv_material", "processor_name": "xatlas_bpy_mock"},
]

_STAGES_3D_SCENE = _STAGES_3D_COMMON + [
    # no rig, no animate for scene
]

_STAGES_3D_CHARACTER = _STAGES_3D_COMMON + [
    {"stage": "rigging", "processor_name": "rigify_mock"},
]

_STAGES_2D = [
    {"stage": "text_to_image", "processor_name": "sdxl_mock"},
    {"stage": "post_process", "processor_name": "rembg_esrgan_mock"},
    {"stage": "format_output", "processor_name": "png_sprite_9patch_mock"},
]

# Cloud mode (real AI)
if _PROCESSOR_MODE == "cloud":
    _STAGES_3D_SCENE = [
        {"stage": "text_to_image", "processor_name": "sdxl_cloud"},
        {"stage": "image_to_3d", "processor_name": "image_to_3d_cloud"},
        {"stage": "mesh_cleanup", "processor_name": "instant_meshes"},
        {"stage": "uv_material", "processor_name": "xatlas_bpy"},
    ]
    _STAGES_3D_CHARACTER = _STAGES_3D_SCENE + [
        {"stage": "rigging", "processor_name": "rigify" if _HAS_BLENDER else "rigify_mock"},
    ]
    _STAGES_2D = [
        {"stage": "text_to_image", "processor_name": "sdxl_cloud"},
        {"stage": "post_process", "processor_name": "rembg_esrgan"},
        {"stage": "format_output", "processor_name": "png_sprite_9patch"},
    ]

# Local/production mode (real AI, no cloud)
elif _PROCESSOR_MODE in ("local", "production"):
    _STAGES_3D_SCENE = [
        {"stage": "text_to_image", "processor_name": "sdxl"},
        {"stage": "image_to_3d", "processor_name": "triposr"},
        {"stage": "mesh_cleanup", "processor_name": "instant_meshes"},
        {"stage": "uv_material", "processor_name": "xatlas_bpy"},
    ]
    _STAGES_3D_CHARACTER = _STAGES_3D_SCENE + [
        {"stage": "rigging", "processor_name": "rigify" if _HAS_BLENDER else "rigify_mock"},
    ]
    _STAGES_2D = [
        {"stage": "text_to_image", "processor_name": "sdxl"},
        {"stage": "post_process", "processor_name": "rembg_esrgan"},
        {"stage": "format_output", "processor_name": "png_sprite_9patch"},
    ]

# PIPELINE_REGISTRY: (processor_mode, pipeline_type) → ordered list of stages
PIPELINE_REGISTRY: dict[tuple[str, str], list[dict[str, str]]] = {
    ("mock", "3d_scene"): _STAGES_3D_SCENE,
    ("mock", "3d_character"): _STAGES_3D_CHARACTER,
    ("mock", "2d_art"): _STAGES_2D,
    ("cloud", "3d_scene"): _STAGES_3D_SCENE,
    ("cloud", "3d_character"): _STAGES_3D_CHARACTER,
    ("cloud", "2d_art"): _STAGES_2D,
    ("local", "3d_scene"): _STAGES_3D_SCENE,
    ("local", "3d_character"): _STAGES_3D_CHARACTER,
    ("local", "2d_art"): _STAGES_2D,
    ("production", "3d_scene"): _STAGES_3D_SCENE,
    ("production", "3d_character"): _STAGES_3D_CHARACTER,
    ("production", "2d_art"): _STAGES_2D,
}


def get_pipeline_stages(pipeline_type: str) -> list[dict[str, str]]:
    """Get the ordered stage list for a pipeline type using the current PROCESSOR_MODE."""
    key = (_PROCESSOR_MODE, pipeline_type)
    if key not in PIPELINE_REGISTRY:
        key = ("mock", pipeline_type)
    return PIPELINE_REGISTRY.get(key, [])


# ── Stage definitions for provider settings UI ─────────────────────────────
# Grouped by pipeline type so the UI can render sections independently.

_STAGE_DEFS_3D_SCENE = [
    {
        "stage": "text_to_image",
        "label": "文生图",
        "description": "从文字提示词生成概念图",
        "modes": [
            {"mode": "mock", "label": "Mock (模拟)", "processor_name": "sdxl_mock"},
            {"mode": "local", "label": "本地模型 (SDXL)", "processor_name": "sdxl"},
            {"mode": "cloud", "label": "云端 API", "processor_name": "sdxl_cloud"},
        ],
        "cloud_providers": ["stability_ai", "fal_ai", "replicate", "comfyui", "volcengine"],
    },
    {
        "stage": "image_to_3d",
        "label": "图生3D",
        "description": "从概念图生成3D模型",
        "modes": [
            {"mode": "mock", "label": "Mock (模拟)", "processor_name": "triposr_mock"},
            {"mode": "local", "label": "本地模型 (TripoSR)", "processor_name": "triposr"},
            {"mode": "cloud", "label": "云端 API", "processor_name": "image_to_3d_cloud"},
        ],
        "cloud_providers": ["tripo_cloud", "meshy_ai", "csm_ai", "volcengine"],
    },
    {
        "stage": "mesh_cleanup",
        "label": "网格清理",
        "description": "清理和优化3D网格拓扑",
        "modes": [
            {"mode": "skip", "label": "跳过", "processor_name": "skip"},
            {"mode": "mock", "label": "Mock (模拟)", "processor_name": "instant_meshes_mock"},
            {"mode": "local", "label": "本地工具 (Instant Meshes)", "processor_name": "instant_meshes"},
        ],
        "cloud_providers": [],
    },
    {
        "stage": "uv_material",
        "label": "UV与材质",
        "description": "UV展开和PBR材质烘焙",
        "modes": [
            {"mode": "skip", "label": "跳过", "processor_name": "skip"},
            {"mode": "mock", "label": "Mock (模拟)", "processor_name": "xatlas_bpy_mock"},
            {"mode": "local", "label": "本地工具 (xatlas + Blender)", "processor_name": "xatlas_bpy"},
        ],
        "cloud_providers": [],
    },
]

_STAGE_DEFS_3D_CHARACTER = _STAGE_DEFS_3D_SCENE + [
    {
        "stage": "rigging",
        "label": "骨骼绑定",
        "description": "自动骨骼绑定和蒙皮",
        "modes": [
            {"mode": "skip", "label": "跳过", "processor_name": "skip"},
            {"mode": "mock", "label": "Mock (模拟)", "processor_name": "rigify_mock"},
            {"mode": "local", "label": "本地工具 (Rigify)", "processor_name": "rigify"},
        ],
        "cloud_providers": [],
    },
]

_STAGE_DEFS_2D = [
    {
        "stage": "text_to_image",
        "label": "文生图",
        "description": "从文字提示词生成概念图",
        "modes": [
            {"mode": "mock", "label": "Mock (模拟)", "processor_name": "sdxl_mock"},
            {"mode": "local", "label": "本地模型 (SDXL)", "processor_name": "sdxl"},
            {"mode": "cloud", "label": "云端 API", "processor_name": "sdxl_cloud"},
        ],
        "cloud_providers": ["stability_ai", "fal_ai", "replicate", "comfyui", "volcengine"],
    },
    {
        "stage": "post_process",
        "label": "后处理 (2D)",
        "description": "去背景、超分辨率等2D后处理",
        "modes": [
            {"mode": "mock", "label": "Mock (模拟)", "processor_name": "rembg_esrgan_mock"},
            {"mode": "local", "label": "本地工具 (rembg + ESRGAN)", "processor_name": "rembg_esrgan"},
        ],
        "cloud_providers": [],
    },
    {
        "stage": "format_output",
        "label": "格式产出 (2D)",
        "description": "输出为PNG/Sprite Sheet/9-Patch格式",
        "modes": [
            {"mode": "mock", "label": "Mock (模拟)", "processor_name": "png_sprite_9patch_mock"},
            {"mode": "local", "label": "本地工具", "processor_name": "png_sprite_9patch"},
        ],
        "cloud_providers": [],
    },
]

# Public API: per-pipeline-type stage definitions
STAGE_DEFINITIONS: dict[str, list[dict]] = {
    "3d_scene": _STAGE_DEFS_3D_SCENE,
    "3d_character": _STAGE_DEFS_3D_CHARACTER,
    "2d_art": _STAGE_DEFS_2D,
}

# Convenience: all stages flat (for lookups by stage name)
_ALL_STAGES_FLAT: list[dict] = []
for _sd_list in STAGE_DEFINITIONS.values():
    for _sd in _sd_list:
        if _sd not in _ALL_STAGES_FLAT:
            _ALL_STAGES_FLAT.append(_sd)


def get_stage_definition(stage: str) -> dict | None:
    """Look up a stage definition by stage name across all pipeline types."""
    for sd in _ALL_STAGES_FLAT:
        if sd["stage"] == stage:
            return sd
    return None


def get_processor_name_for_mode(stage: str, mode: str) -> str:
    """Look up the processor_name for a given stage+mode from STAGE_DEFINITIONS."""
    sd = get_stage_definition(stage)
    if sd:
        for m in sd["modes"]:
            if m["mode"] == mode:
                return m["processor_name"]
    return f"{stage}_{mode}"
