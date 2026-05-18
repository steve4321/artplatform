"""HTTP client for the ArtPlatform API.

Provides helper functions for making authenticated requests to the
ArtPlatform backend API. Auth token is resolved from:
  1. ARTPLATFORM_API_KEY environment variable
  2. ~/.artplatform/credentials file
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

DEFAULT_API_URL = "http://localhost:8000"


def _base_url() -> str:
    return os.environ.get("ARTPLATFORM_API_URL", DEFAULT_API_URL).rstrip("/")


def _read_credentials_file() -> str | None:
    cred_path = Path.home() / ".artplatform" / "credentials"
    if not cred_path.is_file():
        return None
    try:
        data = json.loads(cred_path.read_text(encoding="utf-8"))
        return data.get("api_key") or data.get("token")
    except (json.JSONDecodeError, OSError):
        return None


def _resolve_token() -> str | None:
    token = os.environ.get("ARTPLATFORM_API_KEY")
    if token:
        return token
    return _read_credentials_file()


def _build_client() -> httpx.AsyncClient:
    headers: dict[str, str] = {}
    token = _resolve_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(base_url=_base_url(), headers=headers, timeout=30.0)


async def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    async with _build_client() as client:
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()


async def api_post(path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    async with _build_client() as client:
        resp = await client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()


async def api_patch(path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    async with _build_client() as client:
        resp = await client.patch(path, json=json)
        resp.raise_for_status()
        return resp.json()


async def api_post_file(path: str, file_path: str) -> dict[str, Any]:
    token = _resolve_token()
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(
        base_url=_base_url(), headers=headers, timeout=120.0
    ) as client:
        with open(file_path, "rb") as f:
            filename = Path(file_path).name
            resp = await client.post(
                path,
                files={"file": (filename, f, "application/octet-stream")},
            )
        resp.raise_for_status()
        return resp.json()
