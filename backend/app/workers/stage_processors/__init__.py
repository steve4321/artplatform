import os

_MODE = os.environ.get("PROCESSOR_MODE", "mock").lower()
_LOCAL_DEV = os.environ.get("LOCAL_DEV", "").lower() in ("true", "1", "yes")

if _LOCAL_DEV or _MODE == "mock":
    import app.workers.stage_processors.mock

elif _MODE == "cloud":
    # Initialize providers from env vars BEFORE importing cloud processors
    # (cloud processors create routers that call get_provider())
    from app.ai.router import _init_providers_from_env

    _init_providers_from_env()

    import app.workers.stage_processors.text_to_image_cloud
    import app.workers.stage_processors.image_to_3d_cloud
    import app.workers.stage_processors.cleanup
    import app.workers.stage_processors.uv_material
    import app.workers.stage_processors.rig
    import app.workers.stage_processors.animate

else:
    # _MODE == "local": self-hosted GPU inference (existing processors)
    import app.workers.stage_processors.text_to_image
    import app.workers.stage_processors.image_to_3d
    import app.workers.stage_processors.cleanup
    import app.workers.stage_processors.uv_material
    import app.workers.stage_processors.rig
    import app.workers.stage_processors.animate
    import app.workers.stage_processors.image_captioning
