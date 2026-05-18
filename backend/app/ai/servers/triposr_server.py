"""Self-hosted TripoSR inference server — image-to-3D via HTTP."""

from __future__ import annotations

import logging
import os
import uuid
from io import BytesIO
from typing import Any

import httpx
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TripoSR Inference Server")

_model = None
_device: str | None = None
_load_time: float | None = None


def _get_device() -> str:
    global _device
    if _device is None:
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("TripoSR device: %s", _device)
    return _device


def _load_model():
    global _model, _load_time
    if _model is not None:
        return _model

    model_path = os.environ.get("TRIPOSR_MODEL_PATH", "stabilityai/TripoSR")
    device = _get_device()
    t0 = time.monotonic()

    logger.info("Loading TripoSR from %s on %s …", model_path, device)
    from tsr.models import TSR

    model = TSR.from_pretrained(
        model_path,
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.to(device)
    model.renderer.set_device(device)

    import time as _time
    _load_time = _time.monotonic() - t0
    logger.info("TripoSR loaded in %.1fs", _load_time)
    _model = model
    return _model


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": _model is not None}


@app.get("/stats")
async def stats():
    return {"model_loaded": _model is not None, "device": _get_device(), "load_time_s": _load_time}


def _load_image_from_url(url: str) -> Image.Image:
    with httpx.Client(timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.content
    image = Image.open(BytesIO(data)).convert("RGBA")
    if image.mode == "RGBA":
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background).convert("RGB")
    return image


@app.post("/generate")
async def generate(body: dict[str, Any]):
    model = _load_model()
    device = _get_device()

    image_url = body.get("image_url")
    if not image_url:
        raise HTTPException(status_code=400, detail="image_url required")

    image = _load_image_from_url(image_url)
    resolution = int(body.get("resolution", 256))

    with torch.no_grad():
        scenes = model([image], device=device, image_size=resolution)

    if not scenes or not scenes[0]:
        raise HTTPException(status_code=500, detail="TripoSR returned no meshes")

    scene = scenes[0]

    import numpy as np
    import trimesh

    meshes = scene.meshes if hasattr(scene, "meshes") else [scene]
    verts_list, faces_list, offset = [], [], 0
    for m in meshes:
        v = getattr(m, "vertices", None)
        f = getattr(m, "faces", None)
        if v is None or f is None:
            continue
        v = np.array(v) if not isinstance(v, np.ndarray) else v
        f = np.array(f) if not isinstance(f, np.ndarray) else f
        verts_list.append(v)
        faces_list.append(f + offset)
        offset += len(verts_list[-1])

    if not verts_list:
        raise HTTPException(status_code=500, detail="TripoSR produced no mesh data")

    combined = trimesh.Trimesh(
        vertices=np.concatenate(verts_list, axis=0),
        faces=np.concatenate(faces_list, axis=0),
        process=True,
    )

    out_id = uuid.uuid4().hex
    out_path = f"/tmp/triposr_{out_id}.glb"
    combined.export(out_path, file_type="glb")

    logger.info("TripoSR: %d verts, %d faces", len(combined.vertices), len(combined.faces))
    return FileResponse(out_path, media_type="model/gltf-binary", filename=f"model_{out_id}.glb")


@app.post("/generate_multipart")
async def generate_multipart(file: UploadFile = File(...)):
    model = _load_model()
    device = _get_device()

    data = await file.read()
    image = Image.open(BytesIO(data)).convert("RGBA")
    if image.mode == "RGBA":
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background).convert("RGB")

    with torch.no_grad():
        scenes = model([image], device=device, image_size=256)

    if not scenes or not scenes[0]:
        raise HTTPException(status_code=500, detail="TripoSR returned no meshes")

    scene = scenes[0]

    import numpy as np
    import trimesh

    meshes = scene.meshes if hasattr(scene, "meshes") else [scene]
    verts_list, faces_list, offset = [], [], 0
    for m in meshes:
        v = getattr(m, "vertices", None)
        f = getattr(m, "faces", None)
        if v is None or f is None:
            continue
        v = np.array(v) if not isinstance(v, np.ndarray) else v
        f = np.array(f) if not isinstance(f, np.ndarray) else f
        verts_list.append(v)
        faces_list.append(f + offset)
        offset += len(verts_list[-1])

    combined = trimesh.Trimesh(
        vertices=np.concatenate(verts_list, axis=0),
        faces=np.concatenate(faces_list, axis=0),
        process=True,
    )

    out_id = uuid.uuid4().hex
    out_path = f"/tmp/triposr_{out_id}.glb"
    combined.export(out_path, file_type="glb")

    return FileResponse(out_path, media_type="model/gltf-binary", filename=f"model_{out_id}.glb")


@app.post("/unload")
async def unload():
    global _model
    if _model is not None:
        del _model
        _model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("TripoSR unloaded from GPU")
    return {"status": "unloaded"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
