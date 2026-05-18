"""Shared configuration constants for the CLI."""

from __future__ import annotations

from pathlib import Path

API_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"
CREDENTIALS_FILE = Path.home() / ".artplatform" / "credentials"
