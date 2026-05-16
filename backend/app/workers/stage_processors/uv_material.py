from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register


@register
class UVMaterialXatlasBpy(PipelineProcessor):
    stage = "uv_material"
    name = "xatlas_bpy"
    requires_gpu = False
    estimated_duration_s = 45

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in ("obj", "glb", "gltf", "ply")
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        raise NotImplementedError("xatlas + bpy UV/material worker not yet implemented")
