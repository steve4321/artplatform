from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register


@register
class TextToImageSDXL(PipelineProcessor):
    stage = "text_to_image"
    name = "sdxl"
    requires_gpu = True
    estimated_duration_s = 10

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return bool(config.get("prompt"))

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        raise NotImplementedError("SDXL worker not yet implemented")
