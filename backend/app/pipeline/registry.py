from app.pipeline.processor import PipelineProcessor

PROCESSORS: dict[str, PipelineProcessor] = {}


def register(processor_cls: type[PipelineProcessor]) -> type[PipelineProcessor]:
    instance = processor_cls()
    key = f"{instance.stage}:{instance.name}"
    PROCESSORS[key] = instance
    return processor_cls


def get_processor(stage: str, name: str) -> PipelineProcessor:
    key = f"{stage}:{name}"
    if key not in PROCESSORS:
        raise KeyError(f"No processor registered for {key!r}. Available: {list(PROCESSORS)}")
    return PROCESSORS[key]


def get_processors_for_stage(stage: str) -> list[PipelineProcessor]:
    return [p for p in PROCESSORS.values() if p.stage == stage]
