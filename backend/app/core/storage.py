"""MinIO (S3-compatible) object storage client wrapper."""

from datetime import timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from app.core.config import get_settings


class StorageClient(Protocol):
    """Minimal protocol so callers can depend on an interface, not a concrete class."""

    def upload_file(self, key: str, data: bytes, content_type: str) -> str: ...
    def download_file(self, key: str) -> bytes: ...
    def generate_presigned_url(self, key: str, expires: timedelta | None = None) -> str: ...
    def delete_file(self, key: str) -> None: ...


class MinioStorage:
    """Wrapper around :class:`minio.Minio` with bucket auto-creation.

    All public methods are safe to call after :meth:`ensure_bucket` has run
    (done automatically during application startup).
    """

    def __init__(self) -> None:
        from minio import Minio

        settings = get_settings()
        endpoint = settings.S3_ENDPOINT.replace("http://", "").replace("https://", "")
        self._bucket = settings.S3_BUCKET
        self._client = Minio(
            endpoint,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_ENDPOINT.startswith("https"),
            region=settings.S3_REGION,
        )

    # ── Bucket management ─────────────────────────────────────────────────

    async def ensure_bucket(self) -> None:
        """Create the bucket if it does not already exist."""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    # ── CRUD operations ───────────────────────────────────────────────────

    def upload_file(self, key: str, data: bytes, content_type: str) -> str:
        """Upload *data* to *key* and return the storage key.

        Parameters
        ----------
        key:
            Object key (path inside the bucket), e.g. ``"assets/abc/model.glb"``.
        data:
            Raw bytes to upload.
        content_type:
            MIME type, e.g. ``"model/gltf-binary"``.

        Returns
        -------
        str
            The *key* that was written (for later retrieval).
        """
        from io import BytesIO

        self._client.put_object(
            bucket_name=self._bucket,
            object_name=key,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return key

    def download_file(self, key: str) -> bytes:
        """Download an object by *key* and return its bytes.

        Raises
        ------
        S3Error
            If the object does not exist.
        """
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def generate_presigned_url(self, key: str, expires: timedelta | None = None) -> str:
        """Return a pre-signed GET URL for *key*.

        Parameters
        ----------
        key:
            Object key.
        expires:
            How long the URL stays valid.  Defaults to 1 hour.

        Returns
        -------
        str
            A signed URL that can be shared with clients.
        """
        if expires is None:
            expires = timedelta(hours=1)
        return self._client.presigned_get_object(self._bucket, key, expires=expires)

    def delete_file(self, key: str) -> None:
        """Delete an object by *key*.

        Silently succeeds if the object does not exist.
        """
        self._client.remove_object(self._bucket, key)


class LocalStorage:
    """Filesystem-backed storage that mirrors the StorageClient interface.

    Files are stored under ``backend/.local_dev/storage/<bucket>/<key>``.
    Used when ``LOCAL_DEV=true`` so no MinIO server is needed.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._root = settings.local_dev_storage_dir / settings.S3_BUCKET

    async def ensure_bucket(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def upload_file(self, key: str, data: bytes, content_type: str) -> str:
        path = self._resolve(key)
        path.write_bytes(data)
        return key

    def download_file(self, key: str) -> bytes:
        path = self._root / key
        if not path.exists():
            raise FileNotFoundError(f"Storage object not found: {key}")
        return path.read_bytes()

    def generate_presigned_url(self, key: str, expires: timedelta | None = None) -> str:
        return f"/local-storage/{quote(key, safe='/')}"

    def delete_file(self, key: str) -> None:
        path = self._root / key
        if path.exists():
            path.unlink()


# ── Module-level singleton helpers ────────────────────────────────────────

_storage: MinioStorage | LocalStorage | None = None


def get_storage() -> MinioStorage | LocalStorage:
    """Return the storage singleton (created on first call)."""
    global _storage  # noqa: PLW0603
    if _storage is None:
        settings = get_settings()
        _storage = LocalStorage() if settings.LOCAL_DEV else MinioStorage()
    return _storage


async def init_storage() -> None:
    """Initialise the storage client and ensure the bucket exists."""
    client = get_storage()
    await client.ensure_bucket()
