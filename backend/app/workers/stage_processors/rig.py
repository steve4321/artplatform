from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register


@register
class RigRigify(PipelineProcessor):
    stage = "rig"
    name = "rigify"
    requires_gpu = False
    estimated_duration_s = 60

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in ("obj", "glb", "gltf", "fbx")
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        raise NotImplementedError("Rigify worker not yet implemented")
