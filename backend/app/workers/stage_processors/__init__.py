import logging
import os

logger = logging.getLogger(__name__)

_MODE = os.environ.get("PROCESSOR_MODE", "mock").lower()
_LOCAL_DEV = os.environ.get("LOCAL_DEV", "").lower() in ("true", "1", "yes")

import app.workers.stage_processors.mock

if _MODE == "mock":
    pass

elif _MODE == "cloud":
    from app.ai.router import _init_providers_from_env
    _init_providers_from_env()

    import app.workers.stage_processors.text_to_image_cloud
    import app.workers.stage_processors.image_to_3d_cloud
    import app.workers.stage_processors.cleanup
    import app.workers.stage_processors.uv_material

    try:
        import bpy  # noqa: F401
        import app.workers.stage_processors.rig
        import app.workers.stage_processors.animate
    except ImportError:
        logger.warning("bpy not available — rig/animate stages will use mock processors")

else:
    # _MODE == "local": self-hosted GPU inference
    import app.workers.stage_processors.text_to_image

    try:
        import app.workers.stage_processors.image_to_3d_triposr
    except Exception as e:
        logger.warning("TripoSR not available (%s) — image_to_3d will use mock", e)

    import app.workers.stage_processors.cleanup
    import app.workers.stage_processors.uv_material

    try:
        import bpy  # noqa: F401
        import app.workers.stage_processors.rig
        import app.workers.stage_processors.animate
    except ImportError:
        logger.warning("bpy not available — rig/animate stages will use mock processors")

    try:
        import app.workers.stage_processors.image_captioning
    except ImportError:
        logger.warning("image_captioning dependencies not available")
