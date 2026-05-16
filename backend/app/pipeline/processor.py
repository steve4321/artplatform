from abc import ABC, abstractmethod


class PipelineProcessor(ABC):
    stage: str
    name: str
    requires_gpu: bool
    estimated_duration_s: int

    @abstractmethod
    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        ...

    @abstractmethod
    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        ...
