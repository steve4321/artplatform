import logging
import os
import tempfile
import time
import uuid
from uuid import UUID

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.database import _set_sqlite_wal
from app.core.storage import MinioStorage, get_storage
from app.models.pipeline import PipelineRun, PipelineStep
from app.models import Asset
from app.models.asset_version import AssetVersion
from app.pipeline.registry import get_processor
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = None
_sync_session_factory: sessionmaker[Session] | None = None


def _set_sqlite_wal(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        if settings.LOCAL_DEV:
            sync_url = settings.effective_database_url.replace("+aiosqlite", "")
        else:
            sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_url, echo=settings.DEBUG, pool_size=3, max_overflow=5)
        if sync_url.startswith("sqlite"):
            event.listen(_sync_engine, "connect", _set_sqlite_wal)
    return _sync_engine


def _get_sync_session() -> Session:
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(bind=_get_sync_engine(), expire_on_commit=False)
    return _sync_session_factory()


def _download_artifacts(
    storage, artifacts: list[dict], work_dir: str
) -> list[dict]:
    resolved = []
    for artifact in artifacts:
        key = artifact["storage_key"]
        fmt = artifact.get("file_format", os.path.splitext(key)[1].lstrip("."))
        local_path = os.path.join(work_dir, os.path.basename(key))
        data = storage.download_file(key)
        with open(local_path, "wb") as f:
            f.write(data)
        resolved.append({**artifact, "_local_path": local_path, "file_format": fmt})
    return resolved


def _upload_artifacts(
    storage, artifacts: list[dict], pipeline_run_id: str, stage: str
) -> list[dict]:
    uploaded = []
    for artifact in artifacts:
        local_path = artifact.get("_local_path") or artifact.get("local_path")
        if not local_path or not os.path.isfile(local_path):
            logger.warning("Skipping artifact with missing local file: %s", artifact)
            continue
        ext = os.path.splitext(local_path)[1]
        key = f"pipelines/{pipeline_run_id}/{stage}/{uuid.uuid4().hex}{ext}"
        with open(local_path, "rb") as f:
            data = f.read()
        content_type = artifact.get("content_type", "application/octet-stream")
        storage.upload_file(key, data, content_type)
        uploaded.append({
            "storage_key": key,
            "file_format": artifact.get("file_format", ext.lstrip(".")),
            "metadata": artifact.get("metadata", {}),
        })
    return uploaded


@celery_app.task(bind=True)
def run_pipeline(self, pipeline_run_id: str) -> None:
    session = _get_sync_session()
    storage = get_storage()
    run_id = UUID(pipeline_run_id)

    try:
        pipeline_run = session.get(PipelineRun, run_id)
        if pipeline_run is None:
            logger.error("PipelineRun %s not found", pipeline_run_id)
            return

        pipeline_run.status = "running"
        session.commit()

        steps = (
            session.query(PipelineStep)
            .filter(PipelineStep.pipeline_run_id == run_id)
            .order_by(PipelineStep.stage_order)
            .all()
        )

        if not steps:
            logger.error("No steps found for PipelineRun %s", pipeline_run_id)
            pipeline_run.status = "failed"
            session.commit()
            return

        carry_over_artifacts: list[dict] = []
        concept_image_artifacts: list[dict] = []
        if pipeline_run.reference_image_key:
            carry_over_artifacts.append({
                "storage_key": pipeline_run.reference_image_key,
                "file_format": "png",
                "metadata": {"source": "reference_image"},
            })

        completed = 0
        last_successful_step = None

        for step in steps:
            step.status = "running"
            session.commit()

            processor = get_processor(step.stage, step.processor_name)
            stage_config = step.config or {}
            stage_config.setdefault("prompt", pipeline_run.prompt)

            with tempfile.TemporaryDirectory(prefix=f"pipe_{step.stage}_") as work_dir:
                try:
                    local_inputs = _download_artifacts(storage, carry_over_artifacts, work_dir)

                    if step.stage == "uv_material" and concept_image_artifacts:
                        concept_local = _download_artifacts(storage, concept_image_artifacts, work_dir)
                        local_inputs.extend(concept_local)

                    if not processor.can_run(local_inputs, stage_config):
                        step.status = "skipped"
                        step.error_message = "Preconditions not met"
                        session.commit()
                        continue

                    t0 = time.monotonic()
                    raw_outputs = processor.run(local_inputs, stage_config, work_dir)
                    elapsed_ms = int((time.monotonic() - t0) * 1000)

                    uploaded = _upload_artifacts(
                        storage, raw_outputs, str(pipeline_run.id), step.stage
                    )

                    step.status = "completed"
                    step.duration_ms = elapsed_ms
                    step.output_artifact_ids = [a["storage_key"] for a in uploaded]
                    session.commit()

                    if step.stage == "text_to_image" and not concept_image_artifacts:
                        for a in uploaded:
                            if a.get("file_format") == "png":
                                concept_image_artifacts.append({
                                    **a,
                                    "metadata": {
                                        **a.get("metadata", {}),
                                        "source": "concept_image",
                                        "stage": "text_to_image",
                                    },
                                })

                        is_3d = pipeline_run.config.get("pipeline_type", "3d_character") != "2d_art"
                        if is_3d and concept_image_artifacts:
                            pipeline_run.completed_stages = completed
                            pipeline_run.status = "paused"
                            session.commit()
                            logger.info("Pipeline %s paused after text_to_image — awaiting concept selection", pipeline_run_id)
                            return

                    carry_over_artifacts = uploaded
                    last_successful_step = step
                    completed += 1

                except Exception as exc:
                    elapsed_ms = int((time.monotonic() - t0) * 1000) if "t0" in dir() else None
                    step.status = "failed"
                    step.duration_ms = elapsed_ms
                    step.error_message = _truncate_error(str(exc))
                    session.commit()

                    pipeline_run.completed_stages = completed
                    pipeline_run.status = "partial" if completed > 0 else "failed"
                    if pipeline_run.asset:
                        pipeline_run.asset.state = "deprecated"
                    session.commit()
                    return

        pipeline_run.completed_stages = completed
        pipeline_run.status = "completed"
        pipeline_run.asset.state = "review"

        if carry_over_artifacts and pipeline_run.asset and last_successful_step and last_successful_step.output_artifact_ids:
            asset = pipeline_run.asset
            version_number = asset.current_version or 1
            # Find the primary model file (GLB) — skip texture PNGs to avoid UNIQUE constraint
            model_extensions = {"glb", "gltf", "fbx", "obj", "ply"}
            primary_key = None
            for storage_key in last_successful_step.output_artifact_ids:
                ext = os.path.splitext(storage_key)[1].lstrip(".").lower()
                if ext in model_extensions:
                    primary_key = storage_key
                    break
            if primary_key is None:
                primary_key = last_successful_step.output_artifact_ids[0]
            ext = os.path.splitext(primary_key)[1].lstrip(".").lower() or "bin"
            version = AssetVersion(
                asset_id=asset.id,
                version=version_number,
                storage_key=primary_key,
                file_format=ext,
                source_type="ai_pipeline",
                pipeline_run_id=pipeline_run.id,
            )
            session.add(version)

        session.commit()

    except Exception:
        logger.exception("Fatal error in run_pipeline for %s", pipeline_run_id)
        try:
            pipeline_run = session.get(PipelineRun, UUID(pipeline_run_id))
            if pipeline_run is not None:
                pipeline_run.status = "failed"
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()


@celery_app.task(bind=True, name="pipeline.resume")
def resume_pipeline(self, pipeline_run_id: str) -> None:
    settings = get_settings()
    sync_url = settings.effective_database_url.replace("+aiosqlite", "")
    sync_engine = create_engine(sync_url, echo=False, pool_pre_ping=True)
    if sync_url.startswith("sqlite"):
        event.listen(sync_engine, "connect", _set_sqlite_wal)
    session_factory = sessionmaker(bind=sync_engine, expire_on_commit=False)

    storage = get_storage()
    session = session_factory()

    try:
        pipeline_run = session.get(PipelineRun, UUID(pipeline_run_id))
        if pipeline_run is None:
            logger.error("PipelineRun %s not found", pipeline_run_id)
            return

        if pipeline_run.status != "paused":
            logger.error("Pipeline %s is not paused (status=%s)", pipeline_run_id, pipeline_run.status)
            return

        pipeline_run.status = "running"
        session.commit()

        steps = (
            session.query(PipelineStep)
            .filter(PipelineStep.pipeline_run_id == UUID(pipeline_run_id))
            .order_by(PipelineStep.stage_order)
            .all()
        )

        selected_idx = pipeline_run.config.get("selected_image_index", 0)

        text_to_image_step = None
        for step in steps:
            if step.stage == "text_to_image":
                text_to_image_step = step
                break

        if text_to_image_step is None or not text_to_image_step.output_artifact_ids:
            logger.error("No text_to_image outputs found for pipeline %s", pipeline_run_id)
            pipeline_run.status = "failed"
            session.commit()
            return

        png_artifacts = [k for k in text_to_image_step.output_artifact_ids if k.lower().endswith(".png")]
        if selected_idx >= len(png_artifacts):
            selected_idx = 0

        selected_key = png_artifacts[selected_idx]
        carry_over_artifacts = [{
            "storage_key": selected_key,
            "file_format": "png",
            "metadata": {"source": "concept_image", "stage": "text_to_image", "selected": True},
        }]

        logger.info("Resuming pipeline %s from stage 2 with image %d: %s", pipeline_run_id, selected_idx, selected_key)

        remaining_steps = [s for s in steps if s.stage_order > text_to_image_step.stage_order]
        completed = 1
        last_successful_step = text_to_image_step

        for step in remaining_steps:
            step.status = "running"
            session.commit()

            processor = get_processor(step.stage, step.processor_name)
            stage_config = step.config or {}
            stage_config.setdefault("prompt", pipeline_run.prompt)

            with tempfile.TemporaryDirectory(prefix=f"resume_{step.stage}_") as work_dir:
                try:
                    local_inputs = _download_artifacts(storage, carry_over_artifacts, work_dir)

                    if step.stage == "uv_material":
                        concept_local = _download_artifacts(storage, carry_over_artifacts, work_dir)
                        local_inputs.extend(concept_local)

                    if not processor.can_run(local_inputs, stage_config):
                        step.status = "skipped"
                        step.error_message = "Preconditions not met"
                        session.commit()
                        continue

                    t0 = time.monotonic()
                    raw_outputs = processor.run(local_inputs, stage_config, work_dir)
                    elapsed_ms = int((time.monotonic() - t0) * 1000)

                    uploaded = _upload_artifacts(
                        storage, raw_outputs, str(pipeline_run.id), step.stage
                    )

                    step.status = "completed"
                    step.duration_ms = elapsed_ms
                    step.output_artifact_ids = [a["storage_key"] for a in uploaded]
                    session.commit()

                    carry_over_artifacts = uploaded
                    last_successful_step = step
                    completed += 1

                except Exception as exc:
                    elapsed_ms = int((time.monotonic() - t0) * 1000) if "t0" in dir() else None
                    step.status = "failed"
                    step.duration_ms = elapsed_ms
                    step.error_message = _truncate_error(str(exc))
                    session.commit()

                    pipeline_run.completed_stages = completed
                    pipeline_run.status = "partial" if completed > 0 else "failed"
                    if pipeline_run.asset:
                        pipeline_run.asset.state = "deprecated"
                    session.commit()
                    return

        pipeline_run.completed_stages = completed
        pipeline_run.status = "completed"
        pipeline_run.asset.state = "review"

        if carry_over_artifacts and pipeline_run.asset and last_successful_step and last_successful_step.output_artifact_ids:
            asset = pipeline_run.asset
            version_number = asset.current_version or 1
            model_extensions = {"glb", "gltf", "fbx", "obj", "ply"}
            primary_key = None
            for storage_key in last_successful_step.output_artifact_ids:
                ext = os.path.splitext(storage_key)[1].lstrip(".").lower()
                if ext in model_extensions:
                    primary_key = storage_key
                    break
            if primary_key is None:
                primary_key = last_successful_step.output_artifact_ids[0]
            ext = os.path.splitext(primary_key)[1].lstrip(".").lower() or "bin"
            version = AssetVersion(
                asset_id=asset.id,
                version=version_number,
                storage_key=primary_key,
                file_format=ext,
                source_type="ai_pipeline",
                pipeline_run_id=pipeline_run.id,
            )
            session.add(version)

        session.commit()

    except Exception:
        logger.exception("Fatal error in resume_pipeline for %s", pipeline_run_id)
        try:
            pipeline_run = session.get(PipelineRun, UUID(pipeline_run_id))
            if pipeline_run is not None:
                pipeline_run.status = "failed"
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()


def _truncate_error(msg: str, limit: int = 2000) -> str:
    return msg[:limit] + "..." if len(msg) > limit else msg
