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
    import app.workers.stage_processors.rig
    import app.workers.stage_processors.animate

    try:
        import app.workers.stage_processors.postprocess_2d
        import app.workers.stage_processors.format_output_2d
    except ImportError:
        logger.warning("2D postprocessing dependencies not available — using mock processors")

else:
    # _MODE == "local": self-hosted GPU inference
    import app.workers.stage_processors.text_to_image

    try:
        import app.workers.stage_processors.image_to_3d_triposr
    except Exception as e:
        logger.warning("TripoSR not available (%s) — image_to_3d will use mock", e)

    import app.workers.stage_processors.cleanup
    import app.workers.stage_processors.uv_material
    import app.workers.stage_processors.rig
    import app.workers.stage_processors.animate

    try:
        import app.workers.stage_processors.image_captioning
    except ImportError:
        logger.warning("image_captioning dependencies not available")

    try:
        import app.workers.stage_processors.postprocess_2d
        import app.workers.stage_processors.format_output_2d
    except ImportError:
        logger.warning("2D postprocessing dependencies not available — using mock processors")
