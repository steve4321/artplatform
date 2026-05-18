"""Provider 注册表和路由器 — 负责 Provider 实例化和路由选择。"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ai.base import GenerationParams, ModelProvider, Stage

logger = logging.getLogger(__name__)

# 全局 Provider 注册表: name → ModelProvider instance
_PROVIDERS: dict[str, "ModelProvider"] = {}


def register_provider(name: str, provider: "ModelProvider") -> None:
    """注册一个 Provider 实例。"""
    _PROVIDERS[name] = provider
    logger.info("Registered AI provider: %s (%s)", name, provider.__class__.__name__)


def get_provider(name: str) -> "ModelProvider":
    """获取已注册的 Provider 实例。"""
    if name not in _PROVIDERS:
        raise ValueError(
            f"Unknown provider: '{name}'. "
            f"Available: {list(_PROVIDERS.keys())}"
        )
    return _PROVIDERS[name]


def list_providers() -> list[str]:
    """返回所有已注册的 Provider 名称。"""
    return list(_PROVIDERS.keys())


def _init_providers_from_env():
    """从环境变量初始化所有已配置的 Provider。
    
    扫描所有已知的 Provider，尝试用环境变量初始化。
    只要对应 API key 存在，就注册。
    """
    import os
    
    # Text-to-Image Providers
    if api_key := os.environ.get("STABILITY_API_KEY"):
        from app.ai.providers.stability_ai import StabilityAIProvider
        register_provider("stability_ai", StabilityAIProvider.from_env())
    
    if api_key := os.environ.get("FAL_API_KEY"):
        from app.ai.providers.fal_ai import FalAIProvider
        register_provider("fal_ai", FalAIProvider.from_env())
    
    if api_key := os.environ.get("REPLICATE_API_KEY"):
        from app.ai.providers.replicate import ReplicateProvider
        register_provider("replicate", ReplicateProvider.from_env())
    
    # Image-to-3D Providers
    if api_key := os.environ.get("TRIPO_API_KEY"):
        from app.ai.providers.tripo_cloud import TripoCloudProvider
        register_provider("tripo_cloud", TripoCloudProvider.from_env())
    
    if api_key := os.environ.get("MESHY_API_KEY"):
        from app.ai.providers.meshy_ai import MeshyAIProvider
        register_provider("meshy_ai", MeshyAIProvider.from_env())
    
    if api_key := os.environ.get("CSM_API_KEY"):
        from app.ai.providers.csm_ai import CSMAIProvider
        register_provider("csm_ai", CSMAIProvider.from_env())
    
    # Self-hosted Providers
    if os.environ.get("SELF_HOSTED_SDXL"):
        from app.ai.providers.self_hosted import SelfHostedSDXLProvider
        register_provider("self_hosted_sdxl", SelfHostedSDXLProvider.from_env())
    
    if os.environ.get("SELF_HOSTED_TRIPOSR"):
        from app.ai.providers.self_hosted import SelfHostedTripoSRProvider
        register_provider("self_hosted_triposr", SelfHostedTripoSRProvider.from_env())
    
    if os.environ.get("COMFYUI_URL"):
        from app.ai.providers.comfyui import ComfyUIProvider
        register_provider("comfyui", ComfyUIProvider.from_env())
    
    logger.info("Initialized %d AI providers: %s", len(_PROVIDERS), list(_PROVIDERS.keys()))


# 启动时自动初始化（延迟导入避免循环依赖）
def _autoload():
    import os
    # 只在非 LOCAL_DEV 且非 mock 模式时自动加载
    if os.environ.get("LOCAL_DEV", "").lower() in ("true", "1", "yes"):
        return
    if os.environ.get("PROCESSOR_MODE", "mock") == "mock":
        return
    _init_providers_from_env()


def create_router(stage: "Stage") -> "ProviderRouter | None":
    """根据管线阶段创建配置好的路由器。
    
    从环境变量读取该阶段的 primary 和 fallbacks 配置。
    """
    from app.ai.base import ProviderRouter
    
    stage_name = stage.value
    
    primary_env = f"{stage_name.upper().replace('_', '_')}_PROVIDER"
    fallback_env = f"{stage_name.upper().replace('_', '_')}_FALLBACKS"
    
    primary = os.environ.get(primary_env)
    fallback_str = os.environ.get(fallback_env, "")
    fallbacks = [f.strip() for f in fallback_str.split(",") if f.strip()] if fallback_str else []
    
    if not primary and not fallbacks:
        return None
    
    return ProviderRouter(
        primary=primary or fallbacks[0] if fallbacks else "stability_ai",
        fallbacks=fallbacks,
        cost_priority=os.environ.get("PROVIDER_COST_PRIORITY", "false").lower() == "true",
    )
