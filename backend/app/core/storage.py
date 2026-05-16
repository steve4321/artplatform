"""MinIO (S3-compatible) object storage client wrapper."""

from datetime import timedelta
from typing import Protocol

from minio import Minio
from minio.error import S3Error

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


# ── Module-level singleton helpers ────────────────────────────────────────

_storage: MinioStorage | None = None


def get_storage() -> MinioStorage:
    """Return the storage singleton (created on first call)."""
    global _storage  # noqa: PLW0603
    if _storage is None:
        _storage = MinioStorage()
    return _storage


async def init_storage() -> None:
    """Initialise the storage client and ensure the bucket exists."""
    client = get_storage()
    await client.ensure_bucket()
