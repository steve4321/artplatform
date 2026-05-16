from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register


@register
class CleanupInstantMeshes(PipelineProcessor):
    stage = "cleanup"
    name = "instant_meshes"
    requires_gpu = False
    estimated_duration_s = 20

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in ("obj", "glb", "gltf", "ply")
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        raise NotImplementedError("Instant Meshes worker not yet implemented")
