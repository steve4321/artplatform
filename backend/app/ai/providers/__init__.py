"""AI Provider implementations — cloud APIs and self-hosted inference."""

from app.ai.providers.stability_ai import StabilityAIProvider
from app.ai.providers.fal_ai import FalAIProvider
from app.ai.providers.replicate import ReplicateProvider
from app.ai.providers.tripo_cloud import TripoCloudProvider
from app.ai.providers.meshy_ai import MeshyAIProvider
from app.ai.providers.csm_ai import CSMAIProvider
from app.ai.providers.self_hosted import (
    SelfHostedSDXLProvider,
    SelfHostedTripoSRProvider,
)
from app.ai.providers.comfyui import ComfyUIProvider

__all__ = [
    "StabilityAIProvider",
    "FalAIProvider",
    "ReplicateProvider",
    "TripoCloudProvider",
    "MeshyAIProvider",
    "CSMAIProvider",
    "SelfHostedSDXLProvider",
    "SelfHostedTripoSRProvider",
    "ComfyUIProvider",
]