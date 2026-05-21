"""Stage processor auto-registration.

All available processors are imported and registered. Processors whose
dependencies are missing (e.g. torch for local GPU inference) are silently
skipped so the application still starts.
"""
import importlib
import logging

logger = logging.getLogger(__name__)

import app.workers.stage_processors.mock

_PROCESSOR_MODULES = [
    "app.workers.stage_processors.text_to_image",
    "app.workers.stage_processors.image_to_3d_triposr",
    "app.workers.stage_processors.text_to_image_cloud",
    "app.workers.stage_processors.image_to_3d_cloud",
    "app.workers.stage_processors.cleanup",
    "app.workers.stage_processors.uv_material",
    "app.workers.stage_processors.rig",
    "app.workers.stage_processors.animate",
    "app.workers.stage_processors.postprocess_2d",
    "app.workers.stage_processors.format_output_2d",
    "app.workers.stage_processors.image_captioning",
]

for _mod_name in _PROCESSOR_MODULES:
    try:
        importlib.import_module(_mod_name)
    except Exception as exc:
        logger.debug("Skipping %s: %s", _mod_name, exc)
