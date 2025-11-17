"""
Object storage client for S3-compatible storage (MinIO).

Provides async operations for file upload, download, deletion, and presigned URLs.
"""
import hashlib
from datetime import datetime, timedelta
from typing import AsyncIterator, BinaryIO, Dict, List, Optional

import aioboto3
import structlog
from botocore.exceptions import ClientError

from backend.core.config import settings
from backend.integrations.storage_exceptions import (
    DownloadError,
    FileNotFoundError,
    StorageError,
    UploadError,
)

logger = structlog.get_logger(__name__)


class StreamingHasher:
    """
    Async iterator that streams file content while computing SHA-256 hash.

    This enables true streaming uploads to S3 without buffering the entire
    file in memory, while simultaneously computing the checksum in a single pass.
    """

    def __init__(self, file_obj: BinaryIO, chunk_size: int, capture_preview: int = 0):
        """
        Initialize streaming hasher.

        Args:
            file_obj: File-like object to stream from
            chunk_size: Size of chunks to read
            capture_preview: Number of bytes to capture for preview (0 to disable)
        """
        self.file_obj = file_obj
        self.chunk_size = chunk_size
        self.hasher = hashlib.sha256()
        self.total_size = 0
        self._exhausted = False
        self.capture_preview = capture_preview
        self.preview_bytes = b""
        self._preview_captured = False

    def __aiter__(self):
        """Return self as async iterator."""
        return self

    async def __anext__(self) -> bytes:
        """
        Read next chunk, update hash, capture preview if needed, and return chunk.

        Returns:
            Next chunk of bytes

        Raises:
            StopAsyncIteration: When file is exhausted
        """
        if self._exhausted:
            raise StopAsyncIteration

        # Read chunk from file (handle both sync and async file objects)
        if hasattr(self.file_obj, 'read'):
            chunk = self.file_obj.read(self.chunk_size)
            # If read returns awaitable, await it
            if hasattr(chunk, '__await__'):
                chunk = await chunk
        else:
            raise StopAsyncIteration

        # Check if we've reached end of file
        if not chunk or len(chunk) == 0:
            self._exhausted = True
            raise StopAsyncIteration

        # Capture preview bytes if requested and not yet captured
        if self.capture_preview > 0 and not self._preview_captured:
            bytes_needed = self.capture_preview - len(self.preview_bytes)
            if bytes_needed > 0:
                self.preview_bytes += chunk[:bytes_needed]
                if len(self.preview_bytes) >= self.capture_preview:
                    self._preview_captured = True

        # Update hash and size tracking
        self.hasher.update(chunk)
        self.total_size += len(chunk)

        return chunk

    def get_checksum(self) -> str:
        """
        Get final SHA-256 checksum.

        Returns:
            Hex digest of SHA-256 hash
        """
        return self.hasher.hexdigest()

    def get_size(self) -> int:
        """
        Get total bytes read.

        Returns:
            Total size in bytes
        """
        return self.total_size

    def get_preview(self) -> bytes:
        """
        Get captured preview bytes.

        Returns:
            Preview bytes (up to capture_preview length)
        """
        return self.preview_bytes


class ObjectStorageClient:
    """Client for S3-compatible object storage operations."""

    def __init__(self):
        """Initialize object storage client with settings from config."""
        self.endpoint_url = f"{'https' if settings.minio_use_ssl else 'http'}://{settings.minio_endpoint}"
        self.access_key = settings.minio_access_key
        self.secret_key = settings.minio_secret_key
        self.region = settings.minio_region
        self.bucket_samples = settings.minio_bucket_samples
        self.bucket_tas = settings.minio_bucket_tas
        self.bucket_debug = settings.minio_bucket_debug
        self.session = aioboto3.Session()

        logger.info(
            "object_storage_client_initialized",
            endpoint=self.endpoint_url,
            region=self.region,
            buckets={
                "samples": self.bucket_samples,
                "tas": self.bucket_tas,
                "debug": self.bucket_debug,
            },
        )

    def _get_client(self):
        """Get async S3 client context manager."""
        return self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
        )

    async def upload_file_async(
        self,
        file_obj: BinaryIO,
        bucket: str,
        key: str,
        content_type: Optional[str] = None,
        capture_preview: int = 0,
    ) -> Dict[str, any]:
        """
        Upload file to storage bucket with true streaming and checksum calculation.

        This method streams the file to S3 without buffering the entire file in memory,
        while simultaneously computing the SHA-256 checksum in a single pass.
        Memory usage is O(chunk_size) regardless of file size.

        Args:
            file_obj: File-like object to upload (can be async or sync)
            bucket: Target bucket name
            key: Object key (path) in bucket
            content_type: Optional MIME type
            capture_preview: Number of bytes to capture for preview (0 to disable)

        Returns:
            Dict with storage_key, checksum (SHA-256), size, and optionally preview_bytes

        Raises:
            UploadError: On upload failure
        """
        log = logger.bind(bucket=bucket, key=key, content_type=content_type)
        log.info("upload_file_started")

        stream_hasher = None
        try:
            # Create streaming hasher that computes hash while uploading
            chunk_size = settings.upload_chunk_size
            stream_hasher = StreamingHasher(file_obj, chunk_size, capture_preview)

            # Upload to S3 with streaming body
            async with self._get_client() as s3:
                extra_args = {}
                if content_type:
                    extra_args["ContentType"] = content_type

                # Pass the async iterator as Body - S3 will consume it chunk by chunk
                # The StreamingHasher computes hash and tracks size as chunks are read
                await s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=stream_hasher,
                    **extra_args,
                )

            # After upload completes, get final checksum, size, and preview
            checksum = stream_hasher.get_checksum()
            file_size = stream_hasher.get_size()
            preview_bytes = stream_hasher.get_preview()

            log.info(
                "upload_file_completed",
                checksum=checksum,
                size=file_size,
                preview_captured=len(preview_bytes) if capture_preview > 0 else None,
            )

            result = {
                "storage_key": key,
                "checksum": checksum,
                "size": file_size,
            }

            if capture_preview > 0:
                result["preview_bytes"] = preview_bytes

            return result

        except ClientError as e:
            file_size = stream_hasher.get_size() if stream_hasher else 0
            log.error(
                "upload_file_failed",
                error=str(e),
                error_code=e.response.get("Error", {}).get("Code"),
                bytes_uploaded=file_size,
            )
            raise UploadError(bucket, key, e, size=file_size) from e
        except Exception as e:
            file_size = stream_hasher.get_size() if stream_hasher else 0
            log.error(
                "upload_file_unexpected_error",
                error=str(e),
                bytes_uploaded=file_size,
            )
            raise UploadError(bucket, key, e) from e

    async def download_file_async(
        self,
        bucket: str,
        key: str,
    ) -> AsyncIterator[bytes]:
        """
        Download file from storage bucket with streaming.

        Args:
            bucket: Source bucket name
            key: Object key (path) in bucket

        Yields:
            Chunks of file data

        Raises:
            FileNotFoundError: If object doesn't exist
            DownloadError: On download failure
        """
        log = logger.bind(bucket=bucket, key=key)
        log.info("download_file_started")

        try:
            async with self._get_client() as s3:
                response = await s3.get_object(Bucket=bucket, Key=key)

                async with response["Body"] as stream:
                    while chunk := await stream.read(settings.upload_chunk_size):
                        yield chunk

            log.info("download_file_completed")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                log.warning("download_file_not_found")
                raise FileNotFoundError(bucket, key, e) from e
            log.error("download_file_failed", error=str(e), error_code=error_code)
            raise DownloadError(bucket, key, e) from e
        except Exception as e:
            log.error("download_file_unexpected_error", error=str(e))
            raise DownloadError(bucket, key, e) from e

    async def delete_file_async(self, bucket: str, key: str) -> None:
        """
        Delete object from storage bucket.

        Args:
            bucket: Target bucket name
            key: Object key (path) to delete

        Raises:
            StorageError: On deletion failure
        """
        log = logger.bind(bucket=bucket, key=key)
        log.info("delete_file_started")

        try:
            async with self._get_client() as s3:
                await s3.delete_object(Bucket=bucket, Key=key)

            log.info("delete_file_completed")

        except ClientError as e:
            log.error("delete_file_failed", error=str(e), error_code=e.response.get("Error", {}).get("Code"))
            raise StorageError(
                f"Failed to delete file from bucket '{bucket}' with key '{key}'",
                e,
                {"bucket": bucket, "key": key},
            ) from e
        except Exception as e:
            log.error("delete_file_unexpected_error", error=str(e))
            raise StorageError(
                f"Failed to delete file from bucket '{bucket}' with key '{key}'",
                e,
                {"bucket": bucket, "key": key},
            ) from e

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """
        Generate presigned URL for temporary file access.

        Args:
            bucket: Bucket name
            key: Object key
            expires_in: URL expiration time in seconds (default 3600 = 1 hour)

        Returns:
            Presigned URL string

        Raises:
            StorageError: On URL generation failure
        """
        log = logger.bind(bucket=bucket, key=key, expires_in=expires_in)
        log.info("generate_presigned_url_started")

        try:
            async with self._get_client() as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": key},
                    ExpiresIn=expires_in,
                )

            log.info("generate_presigned_url_completed")
            return url

        except ClientError as e:
            log.error("generate_presigned_url_failed", error=str(e))
            raise StorageError(
                f"Failed to generate presigned URL for bucket '{bucket}' key '{key}'",
                e,
                {"bucket": bucket, "key": key},
            ) from e
        except Exception as e:
            log.error("generate_presigned_url_unexpected_error", error=str(e))
            raise StorageError(
                f"Failed to generate presigned URL for bucket '{bucket}' key '{key}'",
                e,
                {"bucket": bucket, "key": key},
            ) from e

    async def get_file_metadata(self, bucket: str, key: str) -> Dict[str, any]:
        """
        Retrieve object metadata.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            Dict with size, last_modified, etag, content_type

        Raises:
            FileNotFoundError: If object doesn't exist
            StorageError: On metadata retrieval failure
        """
        log = logger.bind(bucket=bucket, key=key)
        log.info("get_file_metadata_started")

        try:
            async with self._get_client() as s3:
                response = await s3.head_object(Bucket=bucket, Key=key)

            metadata = {
                "size": response.get("ContentLength"),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag", "").strip('"'),
                "content_type": response.get("ContentType"),
            }

            log.info("get_file_metadata_completed", metadata=metadata)
            return metadata

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey"):
                log.warning("get_file_metadata_not_found")
                raise FileNotFoundError(bucket, key, e) from e
            log.error("get_file_metadata_failed", error=str(e), error_code=error_code)
            raise StorageError(
                f"Failed to get metadata for bucket '{bucket}' key '{key}'",
                e,
                {"bucket": bucket, "key": key},
            ) from e
        except Exception as e:
            log.error("get_file_metadata_unexpected_error", error=str(e))
            raise StorageError(
                f"Failed to get metadata for bucket '{bucket}' key '{key}'",
                e,
                {"bucket": bucket, "key": key},
            ) from e

    async def list_files(
        self,
        bucket: str,
        prefix: Optional[str] = None,
        max_keys: int = 1000,
    ) -> List[Dict[str, any]]:
        """
        List objects in bucket with optional prefix filter.

        Args:
            bucket: Bucket name
            prefix: Optional key prefix filter
            max_keys: Maximum number of keys to return

        Returns:
            List of dicts with key, size, last_modified, etag

        Raises:
            StorageError: On listing failure
        """
        log = logger.bind(bucket=bucket, prefix=prefix, max_keys=max_keys)
        log.info("list_files_started")

        try:
            async with self._get_client() as s3:
                params = {"Bucket": bucket, "MaxKeys": max_keys}
                if prefix:
                    params["Prefix"] = prefix

                response = await s3.list_objects_v2(**params)

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                    "etag": obj.get("ETag", "").strip('"'),
                })

            log.info("list_files_completed", count=len(files))
            return files

        except ClientError as e:
            log.error("list_files_failed", error=str(e))
            raise StorageError(
                f"Failed to list files in bucket '{bucket}'",
                e,
                {"bucket": bucket, "prefix": prefix},
            ) from e
        except Exception as e:
            log.error("list_files_unexpected_error", error=str(e))
            raise StorageError(
                f"Failed to list files in bucket '{bucket}'",
                e,
                {"bucket": bucket, "prefix": prefix},
            ) from e