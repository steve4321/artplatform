from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register


@register
class AnimateHYMotion(PipelineProcessor):
    stage = "animate"
    name = "hy_motion"
    requires_gpu = True
    estimated_duration_s = 120

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in ("glb", "gltf", "fbx")
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        raise NotImplementedError("HY-Motion worker not yet implemented")
