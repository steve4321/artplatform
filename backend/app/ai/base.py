"""Provider abstraction layer — swap AI backends without changing pipeline code."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


# ── Data Classes ──────────────────────────────────────────────────────────────

class Stage(Enum):
    """Pipeline stage this provider supports."""
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_3D = "image_to_3d"
    MESH_CLEANUP = "mesh_cleanup"
    UV_MATERIAL = "uv_material"
    RIGGING = "rigging"
    ANIMATION = "animation"


@dataclass
class GeneratedAsset:
    """统一格式 — Provider 返回的生成结果。
    
    所有 Provider 必须返回这个格式，Processor 负责转换为管线 artifact 格式。
    """
    local_path: str
    file_format: str
    content_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationParams:
    """与 Provider 无关的通用生成参数。
    
    各字段为 None 表示使用 Provider 默认值。
    """
    # 通用参数
    prompt: str = ""
    negative_prompt: str = ""
    num_images: int = 1
    seed: int | None = None
    width: int = 1024
    height: int = 1024
    
    # 推理参数
    steps: int = 30
    guidance_scale: float = 7.5
    
    # 模型选择（Provider 可能不支持）
    model_id: str | None = None
    
    # 额外参数（Provider 特定）
    extra: dict[str, Any] = field(default_factory=dict)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.extra.get(key, default)


@dataclass
class ProviderConfig:
    """Provider 配置 — 从环境变量或配置文件加载。"""
    api_key: str = ""
    base_url: str | None = None
    default_model: str | None = None
    max_retries: int = 3
    timeout: int = 60
    

# ── Abstract Base ────────────────────────────────────────────────────────────

class ModelProvider(ABC):
    """AI 模型提供商抽象。
    
    所有 Provider（云 API / 自托管 / ComfyUI）必须实现此接口。
    这样换 Provider 只需要改配置，不改 Processor 代码。
    
    使用方法:
        config = ProviderConfig(api_key=os.environ["STABILITY_API_KEY"])
        provider = StabilityAIProvider(config)
        assets = provider.generate(GenerationParams(prompt="a cat", num_images=2))
    
    属性:
        name: str — Provider 唯一标识，用于路由和配置
        supports: list[Stage] — 该 Provider 支持的管线阶段
    
    要支持新的 Provider？:
        1. 继承 ModelProvider
        2. 实现 generate() + estimate_cost()
        3. 可选覆盖 health_check()
        4. 在 router.py 注册
    """
    
    name: str = "base"
    supports: list[Stage] = []
    
    def __init__(self, config: ProviderConfig | None = None):
        self.config = config or ProviderConfig()
    
    @abstractmethod
    def generate(self, params: GenerationParams, output_dir: str) -> list[GeneratedAsset]:
        """调用 Provider 生成内容，下载到 output_dir，返回 GeneratedAsset 列表。
        
        Args:
            params: 通用生成参数
            output_dir: 内容写入目录（由 PipelineRunner 提供）
        
        Returns:
            list[GeneratedAsset]: 生成的文件列表，路径为 output_dir 下的相对路径
                （Provider 内部负责下载，调用方不需要关心网络传输）
        
        Raises:
            ProviderError: 生成失败（超时、网络错误等）
        """
        ...
    
    @abstractmethod
    def estimate_cost(self, params: GenerationParams) -> float:
        """估算本次生成费用（美元）。
        
        用于 ProviderRouter.cost_priority 排序。
        如果 Provider 无法估算，返回 0.0。
        """
        return 0.0
    
    def health_check(self) -> bool:
        """检查 Provider 是否可用。
        
        默认实现：检查 api_key 是否配置。
        Override 以实现更复杂的健康检查（如 ping API）。
        """
        return bool(self.config.api_key)
    
    @classmethod
    def from_env(cls) -> "ModelProvider":
        """从环境变量创建 Provider 实例。
        
        子类可以覆盖此方法，从环境变量读取特定配置。
        """
        import os
        api_key = getattr(os.environ, f"{cls.name.upper()}_API_KEY", "")
        return cls(ProviderConfig(api_key=api_key))


class ProviderError(Exception):
    """Provider 调用失败。"""
    pass


class ProviderTimeout(ProviderError):
    """Provider 超时。"""
    pass


class ProviderUnavailable(ProviderError):
    """Provider 不可用（健康检查失败）。"""
    pass


# ── Provider Router ───────────────────────────────────────────────────────────

class ProviderRouter:
    """智能路由 — 支持 Fallback 链 + 成本优先策略。
    
    使用方法:
        router = ProviderRouter(
            primary="stability_ai",
            fallbacks=["fal_ai", "replicate"],
        )
        assets = router.generate(Stage.TEXT_TO_IMAGE, params, output_dir)
    
    Fallback 行为:
        1. 尝试 primary
        2. 成功 → 返回
        3. 失败 → 按顺序尝试 fallbacks
        4. 全部失败 → 抛出最后异常（包含所有错误信息）
    """
    
    def __init__(
        self,
        primary: str,
        fallbacks: list[str] | None = None,
        cost_priority: bool = False,
    ):
        from app.ai.router import get_provider
        self.primary = primary
        self.fallbacks = fallbacks or []
        self.cost_priority = cost_priority
        self._get_provider = get_provider
    
    def _get_candidates(self, params: GenerationParams) -> list[str]:
        """返回按优先级排序的 Provider 名称列表。"""
        candidates = [self.primary] + self.fallbacks
        
        if self.cost_priority:
            # 按成本升序排列（便宜的在前面）
            def sort_key(name: str) -> float:
                try:
                    p = self._get_provider(name)
                    return p.estimate_cost(params)
                except Exception:
                    return float("inf")
            candidates = sorted(candidates, key=sort_key)
        
        return candidates
    
    def generate(
        self,
        stage: Stage,
        params: GenerationParams,
        output_dir: str,
    ) -> list[GeneratedAsset]:
        """生成内容，自动处理 Fallback。"""
        candidates = self._get_candidates(params)
        last_error: Exception | None = None
        
        for provider_name in candidates:
            try:
                provider = self._get_provider(provider_name)
            except ValueError as exc:
                logger.warning("Provider %s not available: %s", provider_name, exc)
                continue
            
            # 检查是否支持此阶段
            if stage not in provider.supports and Stage.IMAGE_TO_3D not in provider.supports:
                # 对于 image_to_3d，有些 provider 命名不同，检查名字包含
                if not any(stage.value in s.value for s in provider.supports):
                    logger.debug("Provider %s does not support %s, skipping", provider_name, stage)
                    continue
            
            # 健康检查
            if not provider.health_check():
                logger.warning("Provider %s health check failed, trying next", provider_name)
                continue
            
            logger.info("Using provider: %s", provider_name)
            
            try:
                results = provider.generate(params, output_dir)
                
                # 补充 provider 元数据
                for r in results:
                    r.metadata["provider"] = provider_name
                
                return results
            
            except ProviderTimeout:
                logger.warning("Provider %s timed out, trying next", provider_name)
                last_error = ProviderTimeout(f"{provider_name}: timeout")
                continue
            
            except Exception as exc:
                logger.warning("Provider %s failed: %s. Trying next...", provider_name, exc)
                last_error = exc
                continue
        
        if last_error:
            raise ProviderError(f"All providers failed. Last error: {last_error}") from last_error
        raise ProviderError(f"No available providers for stage {stage.value}")
