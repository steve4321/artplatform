from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register


@register
class ImageTo3DTripoSR(PipelineProcessor):
    stage = "image_to_3d"
    name = "triposr"
    requires_gpu = True
    estimated_duration_s = 30

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in ("png", "jpg", "jpeg", "webp")
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        raise NotImplementedError("TripoSR worker not yet implemented")
