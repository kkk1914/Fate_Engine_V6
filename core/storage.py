"""Storage backend abstraction for report persistence.

Phase 1.4: Protocol-based storage adapter supporting local filesystem
and Google Cloud Storage (GCS). Extensible to S3, Azure Blob, etc.

Usage:
    from core.storage import get_storage

    storage = get_storage()              # reads from config
    path = storage.save_report("report.md", content)
    text = storage.get_report("report.md")
"""
import os
import logging
from typing import Protocol, runtime_checkable
from config import settings

logger = logging.getLogger(__name__)


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol for report storage backends."""

    def save_report(self, filename: str, content: str, subdir: str = "") -> str:
        """Save report content. Returns the storage path/URI."""
        ...

    def get_report(self, filename: str, subdir: str = "") -> str:
        """Retrieve report content by filename."""
        ...

    def exists(self, filename: str, subdir: str = "") -> bool:
        """Check if a report exists."""
        ...


class LocalStorage:
    """Local filesystem storage (default)."""

    def __init__(self, base_dir: str = "./reports"):
        self.base_dir = base_dir

    def _resolve_path(self, filename: str, subdir: str = "") -> str:
        if subdir:
            return os.path.join(self.base_dir, subdir, filename)
        return os.path.join(self.base_dir, filename)

    def save_report(self, filename: str, content: str, subdir: str = "") -> str:
        path = self._resolve_path(filename, subdir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Report saved: {path} ({len(content):,} chars)")
        return path

    def get_report(self, filename: str, subdir: str = "") -> str:
        path = self._resolve_path(filename, subdir)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def exists(self, filename: str, subdir: str = "") -> bool:
        return os.path.exists(self._resolve_path(filename, subdir))


class GCSStorage:
    """Google Cloud Storage backend.

    Requires google-cloud-storage package and GCS_BUCKET in config.
    Falls back to LocalStorage if bucket is not configured.
    """

    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        try:
            from google.cloud import storage as gcs
            self.client = gcs.Client()
            self.bucket = self.client.bucket(bucket_name)
            logger.info(f"GCS storage initialized: gs://{bucket_name}")
        except ImportError:
            raise ImportError(
                "google-cloud-storage required for GCS backend. "
                "Install: pip install google-cloud-storage"
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to GCS bucket '{bucket_name}': {e}")

    def _blob_path(self, filename: str, subdir: str = "") -> str:
        if subdir:
            return f"{subdir}/{filename}"
        return filename

    def save_report(self, filename: str, content: str, subdir: str = "") -> str:
        blob_path = self._blob_path(filename, subdir)
        blob = self.bucket.blob(blob_path)
        blob.upload_from_string(content, content_type="text/markdown")
        uri = f"gs://{self.bucket_name}/{blob_path}"
        logger.info(f"Report saved to GCS: {uri} ({len(content):,} chars)")
        return uri

    def get_report(self, filename: str, subdir: str = "") -> str:
        blob_path = self._blob_path(filename, subdir)
        blob = self.bucket.blob(blob_path)
        return blob.download_as_text(encoding="utf-8")

    def exists(self, filename: str, subdir: str = "") -> bool:
        blob_path = self._blob_path(filename, subdir)
        return self.bucket.blob(blob_path).exists()


def get_storage() -> StorageBackend:
    """Factory: returns configured storage backend.

    Reads storage_backend and gcs_bucket from config.
    Falls back to LocalStorage if GCS is not configured.
    """
    backend = getattr(settings, "storage_backend", "local")

    if backend == "gcs":
        bucket = getattr(settings, "gcs_bucket", "")
        if not bucket:
            logger.warning("storage_backend=gcs but gcs_bucket is empty. Falling back to local.")
            return LocalStorage()
        try:
            return GCSStorage(bucket)
        except (ImportError, ConnectionError) as e:
            logger.warning(f"GCS init failed ({e}). Falling back to local storage.")
            return LocalStorage()

    return LocalStorage()
