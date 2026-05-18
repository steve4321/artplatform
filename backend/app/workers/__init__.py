# Stage processors are registered lazily on first access via
# ``ensure_processors_registered()``.  This avoids importing heavy
# dependencies (torch, diffusers, etc.) at application startup.
_processors_registered = False


def ensure_processors_registered() -> None:
    """Import all stage processor modules to trigger @register decorators.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _processors_registered
    if _processors_registered:
        return
    import app.workers.stage_processors  # noqa: F401
    _processors_registered = True
