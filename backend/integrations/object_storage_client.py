"""
Object Storage Client

S3-compatible object storage client for managing log samples, TA bundles,
and debug artifacts using MinIO or AWS S3.

Supports both synchronous and asynchronous operations for integration with
FastAPI endpoints and Celery background tasks.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any, BinaryIO, Dict, List, Optional
from uuid import UUID

import boto3
import structlog
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from backend.integrations.storage_exceptions import (
    StorageBucketError,
    StorageConnectionError,
    StorageDownloadError,
    StorageNotFoundError,
    StorageQuotaExceededError,
    StorageRetentionError,
    StorageUploadError,
)
from backend.integrations.storage_utils import (
    format_storage_size,
    get_file_size,
    parse_retention_date,
    sanitize_filename,
    validate_file_size,
)

logger = structlog.get_logger(__name__)


@dataclass
class StorageConfig:
    """Configuration for object storage client."""

    endpoint: str
    access_key: str
    secret_key: str
    use_ssl: bool
    region: str
    bucket_samples: str
    bucket_tas: str
    bucket_debug: str
    retention_enabled: bool
    retention_days: int
    max_upload_size_mb: int
    presigned_url_expiration: int
    multipart_threshold_mb: int
    multipart_chunk_size_mb: int
    connection_timeout: int
    read_timeout: int

    @classmethod
    def from_env(cls) -> "StorageConfig":
        """
        Load configuration from environment variables.

        Returns:
            StorageConfig instance

        Raises:
            ValueError: If required environment variables are missing
        """
        required_vars = [
            "MINIO_ENDPOINT",
            "MINIO_ACCESS_KEY",
            "MINIO_SECRET_KEY",
            "MINIO_BUCKET_SAMPLES",
            "MINIO_BUCKET_TAS",
            "MINIO_BUCKET_DEBUG",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        return cls(
            endpoint=os.getenv("MINIO_ENDPOINT", ""),
            access_key=os.getenv("MINIO_ACCESS_KEY", ""),
            secret_key=os.getenv("MINIO_SECRET_KEY", ""),
            use_ssl=os.getenv("MINIO_USE_SSL", "false").lower() == "true",
            region=os.getenv("MINIO_REGION", "us-east-1"),
            bucket_samples=os.getenv("MINIO_BUCKET_SAMPLES", ""),
            bucket_tas=os.getenv("MINIO_BUCKET_TAS", ""),
            bucket_debug=os.getenv("MINIO_BUCKET_DEBUG", ""),
            retention_enabled=os.getenv("SAMPLE_RETENTION_ENABLED", "true").lower()
            == "true",
            retention_days=int(os.getenv("SAMPLE_RETENTION_DAYS", "30")),
            max_upload_size_mb=int(os.getenv("MINIO_MAX_UPLOAD_SIZE_MB", "500")),
            presigned_url_expiration=int(
                os.getenv("MINIO_PRESIGNED_URL_EXPIRATION", "3600")
            ),
            multipart_threshold_mb=int(
                os.getenv("MINIO_MULTIPART_THRESHOLD_MB", "5")
            ),
            multipart_chunk_size_mb=int(os.getenv("MINIO_MULTIPART_CHUNK_SIZE_MB", "5")),
            connection_timeout=int(os.getenv("MINIO_CONNECTION_TIMEOUT", "30")),
            read_timeout=int(os.getenv("MINIO_READ_TIMEOUT", "60")),
        )

    def validate(self) -> None:
        """
        Validate configuration values.

        Raises:
            ValueError: If configuration values are invalid
        """
        if not self.endpoint:
            raise ValueError("Storage endpoint cannot be empty")

        if not all([self.bucket_samples, self.bucket_tas, self.bucket_debug]):
            raise ValueError("All bucket names must be configured")

        if self.retention_days < 1:
            raise ValueError("Retention days must be at least 1")

        if self.max_upload_size_mb < 1:
            raise ValueError("Max upload size must be at least 1 MB")


class ObjectStorageClient:
    """
    S3-compatible object storage client for managing artifacts.

    Provides methods for uploading, downloading, and managing log samples,
    TA bundles, and debug bundles with retention policy enforcement.
    """

    def __init__(self, config: Optional[StorageConfig] = None):
        """
        Initialize object storage client.

        Args:
            config: Storage configuration (defaults to loading from environment)
        """
        self.config = config or StorageConfig.from_env()
        self.config.validate()

        # Configure boto3 client
        boto_config = Config(
            connect_timeout=self.config.connection_timeout,
            read_timeout=self.config.read_timeout,
            retries={"max_attempts": 3, "mode": "standard"},
            signature_version="s3v4",
        )

        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.config.endpoint,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                region_name=self.config.region,
                use_ssl=self.config.use_ssl,
                config=boto_config,
            )
            logger.info(
                "object_storage_client_initialized",
                endpoint=self.config.endpoint,
                buckets={
                    "samples": self.config.bucket_samples,
                    "tas": self.config.bucket_tas,
                    "debug": self.config.bucket_debug,
                },
            )
        except Exception as e:
            logger.error("failed_to_initialize_storage_client", error=str(e))
            raise StorageConnectionError(
                "Failed to initialize storage client",
                original_exception=e,
                context={"endpoint": self.config.endpoint},
            )

    def initialize_buckets(self) -> Dict[str, bool]:
        """
        Create storage buckets if they don't exist.

        Returns:
            Dictionary mapping bucket names to creation status

        Raises:
            StorageBucketError: If bucket creation fails
        """
        buckets = {
            "samples": self.config.bucket_samples,
            "tas": self.config.bucket_tas,
            "debug": self.config.bucket_debug,
        }

        results = {}

        for bucket_type, bucket_name in buckets.items():
            try:
                # Check if bucket exists
                self.s3_client.head_bucket(Bucket=bucket_name)
                results[bucket_name] = False  # Already exists
                logger.info("bucket_already_exists", bucket=bucket_name, type=bucket_type)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")

                if error_code == "404":
                    # Bucket doesn't exist, create it
                    try:
                        self.s3_client.create_bucket(Bucket=bucket_name)
                        results[bucket_name] = True  # Created
                        logger.info("bucket_created", bucket=bucket_name, type=bucket_type)
                    except ClientError as create_error:
                        logger.error(
                            "bucket_creation_failed",
                            bucket=bucket_name,
                            error=str(create_error),
                        )
                        raise StorageBucketError(
                            f"Failed to create bucket: {bucket_name}",
                            original_exception=create_error,
                            context={"bucket": bucket_name, "type": bucket_type},
                        )
                else:
                    # Other error (permissions, etc.)
                    logger.error(
                        "bucket_access_error", bucket=bucket_name, error=str(e)
                    )
                    raise StorageBucketError(
                        f"Failed to access bucket: {bucket_name}",
                        original_exception=e,
                        context={"bucket": bucket_name, "type": bucket_type},
                    )
            except EndpointConnectionError as e:
                logger.error("storage_endpoint_unreachable", error=str(e))
                raise StorageConnectionError(
                    "Cannot reach storage endpoint",
                    original_exception=e,
                    context={"endpoint": self.config.endpoint},
                )

        return results

    # ==================== Log Sample Operations ====================

    def upload_log_sample(
        self,
        request_id: UUID,
        file_stream: BinaryIO,
        filename: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Upload log sample to storage.

        Args:
            request_id: UUID of the associated request
            file_stream: Binary file stream
            filename: Original filename
            content_type: MIME type of the file
            metadata: Additional metadata tags

        Returns:
            Storage key for the uploaded file

        Raises:
            StorageQuotaExceededError: If file exceeds size limit
            StorageUploadError: If upload fails
        """
        # Validate file size
        if not validate_file_size(file_stream, self.config.max_upload_size_mb):
            file_size = get_file_size(file_stream)
            raise StorageQuotaExceededError(
                f"File size {format_storage_size(file_size)} exceeds limit of {self.config.max_upload_size_mb} MB",
                context={
                    "file_size": file_size,
                    "max_size": self.config.max_upload_size_mb * 1024 * 1024,
                    "filename": filename,
                },
            )

        # Sanitize filename and generate storage key
        safe_filename = sanitize_filename(filename)
        storage_key = self._generate_storage_key("samples", str(request_id), safe_filename)

        # Prepare metadata
        upload_metadata = metadata or {}
        upload_metadata.update(
            {
                "request_id": str(request_id),
                "original_filename": filename,
                "upload_date": datetime.utcnow().isoformat(),
            }
        )

        # Upload file
        try:
            logger.info(
                "uploading_log_sample",
                request_id=str(request_id),
                filename=filename,
                storage_key=storage_key,
            )

            self._stream_upload(
                bucket=self.config.bucket_samples,
                key=storage_key,
                file_stream=file_stream,
                content_type=content_type,
                metadata=upload_metadata,
            )

            logger.info(
                "log_sample_uploaded",
                request_id=str(request_id),
                storage_key=storage_key,
            )
            return storage_key

        except Exception as e:
            logger.error(
                "log_sample_upload_failed",
                request_id=str(request_id),
                error=str(e),
            )
            raise StorageUploadError(
                "Failed to upload log sample",
                original_exception=e,
                context={"request_id": str(request_id), "filename": filename},
            )

    def download_log_sample(self, storage_key: str) -> bytes:
        """
        Download log sample from storage.

        Args:
            storage_key: Storage key of the file

        Returns:
            File contents as bytes

        Raises:
            StorageNotFoundError: If file doesn't exist
            StorageDownloadError: If download fails
        """
        try:
            logger.info("downloading_log_sample", storage_key=storage_key)

            response = self.s3_client.get_object(
                Bucket=self.config.bucket_samples, Key=storage_key
            )
            content = response["Body"].read()

            logger.info("log_sample_downloaded", storage_key=storage_key)
            return content

        except ClientError as e:
            if e.response.get("Error", {}).get("Code", "") == "NoSuchKey":
                raise StorageNotFoundError(
                    "Log sample not found",
                    original_exception=e,
                    context={"storage_key": storage_key},
                )
            raise StorageDownloadError(
                "Failed to download log sample",
                original_exception=e,
                context={"storage_key": storage_key},
            )

    def get_log_sample_presigned_url(
        self, storage_key: str, expiration: Optional[int] = None
    ) -> str:
        """
        Generate presigned URL for secure download of log sample.

        Args:
            storage_key: Storage key of the file
            expiration: URL expiration time in seconds (defaults to config value)

        Returns:
            Presigned URL

        Raises:
            StorageDownloadError: If URL generation fails
        """
        expiration = expiration or self.config.presigned_url_expiration

        try:
            logger.info(
                "generating_presigned_url",
                storage_key=storage_key,
                expiration=expiration,
            )

            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.config.bucket_samples, "Key": storage_key},
                ExpiresIn=expiration,
            )

            logger.info("presigned_url_generated", storage_key=storage_key)
            return url

        except Exception as e:
            logger.error("presigned_url_generation_failed", error=str(e))
            raise StorageDownloadError(
                "Failed to generate presigned URL",
                original_exception=e,
                context={"storage_key": storage_key},
            )

    def delete_log_sample(self, storage_key: str) -> bool:
        """
        Delete log sample from storage.

        Args:
            storage_key: Storage key of the file

        Returns:
            True if deleted successfully

        Raises:
            StorageDownloadError: If deletion fails
        """
        try:
            logger.info("deleting_log_sample", storage_key=storage_key)

            self.s3_client.delete_object(
                Bucket=self.config.bucket_samples, Key=storage_key
            )

            logger.info("log_sample_deleted", storage_key=storage_key)
            return True

        except Exception as e:
            logger.error("log_sample_deletion_failed", error=str(e))
            raise StorageDownloadError(
                "Failed to delete log sample",
                original_exception=e,
                context={"storage_key": storage_key},
            )

    def list_log_samples(self, request_id: UUID) -> List[Dict[str, Any]]:
        """
        List all log samples for a request.

        Args:
            request_id: UUID of the request

        Returns:
            List of sample metadata dictionaries

        Raises:
            StorageDownloadError: If listing fails
        """
        prefix = self._generate_storage_key("samples", str(request_id))

        try:
            logger.info("listing_log_samples", request_id=str(request_id))

            response = self.s3_client.list_objects_v2(
                Bucket=self.config.bucket_samples, Prefix=prefix
            )

            samples = []
            for obj in response.get("Contents", []):
                # Get object metadata
                head = self.s3_client.head_object(
                    Bucket=self.config.bucket_samples, Key=obj["Key"]
                )

                samples.append(
                    {
                        "storage_key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "metadata": head.get("Metadata", {}),
                    }
                )

            logger.info(
                "log_samples_listed",
                request_id=str(request_id),
                count=len(samples),
            )
            return samples

        except Exception as e:
            logger.error("log_samples_listing_failed", error=str(e))
            raise StorageDownloadError(
                "Failed to list log samples",
                original_exception=e,
                context={"request_id": str(request_id)},
            )

    # ==================== TA Bundle Operations ====================

    def upload_ta_bundle(
        self,
        request_id: UUID,
        revision_id: UUID,
        file_stream: BinaryIO,
        version: int,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Upload TA bundle to storage.

        Args:
            request_id: UUID of the associated request
            revision_id: UUID of the TA revision
            file_stream: Binary file stream
            version: TA version number
            metadata: Additional metadata tags

        Returns:
            Storage key for the uploaded bundle

        Raises:
            StorageUploadError: If upload fails
        """
        storage_key = self._generate_storage_key(
            "tas", str(request_id), f"v{version}", f"{revision_id}.tgz"
        )

        upload_metadata = metadata or {}
        upload_metadata.update(
            {
                "request_id": str(request_id),
                "revision_id": str(revision_id),
                "version": str(version),
                "upload_date": datetime.utcnow().isoformat(),
            }
        )

        try:
            logger.info(
                "uploading_ta_bundle",
                request_id=str(request_id),
                version=version,
                storage_key=storage_key,
            )

            self._stream_upload(
                bucket=self.config.bucket_tas,
                key=storage_key,
                file_stream=file_stream,
                content_type="application/gzip",
                metadata=upload_metadata,
            )

            logger.info("ta_bundle_uploaded", storage_key=storage_key)
            return storage_key

        except Exception as e:
            logger.error("ta_bundle_upload_failed", error=str(e))
            raise StorageUploadError(
                "Failed to upload TA bundle",
                original_exception=e,
                context={
                    "request_id": str(request_id),
                    "version": version,
                },
            )

    def download_ta_bundle(self, storage_key: str) -> bytes:
        """
        Download TA bundle from storage.

        Args:
            storage_key: Storage key of the bundle

        Returns:
            Bundle contents as bytes

        Raises:
            StorageNotFoundError: If bundle doesn't exist
            StorageDownloadError: If download fails
        """
        try:
            logger.info("downloading_ta_bundle", storage_key=storage_key)

            response = self.s3_client.get_object(
                Bucket=self.config.bucket_tas, Key=storage_key
            )
            content = response["Body"].read()

            logger.info("ta_bundle_downloaded", storage_key=storage_key)
            return content

        except ClientError as e:
            if e.response.get("Error", {}).get("Code", "") == "NoSuchKey":
                raise StorageNotFoundError(
                    "TA bundle not found",
                    original_exception=e,
                    context={"storage_key": storage_key},
                )
            raise StorageDownloadError(
                "Failed to download TA bundle",
                original_exception=e,
                context={"storage_key": storage_key},
            )

    def get_ta_bundle_presigned_url(
        self, storage_key: str, expiration: Optional[int] = None
    ) -> str:
        """
        Generate presigned URL for TA bundle download.

        Args:
            storage_key: Storage key of the bundle
            expiration: URL expiration time in seconds

        Returns:
            Presigned URL

        Raises:
            StorageDownloadError: If URL generation fails
        """
        expiration = expiration or self.config.presigned_url_expiration

        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.config.bucket_tas, "Key": storage_key},
                ExpiresIn=expiration,
            )
            return url

        except Exception as e:
            raise StorageDownloadError(
                "Failed to generate presigned URL for TA bundle",
                original_exception=e,
                context={"storage_key": storage_key},
            )

    def list_ta_revisions(self, request_id: UUID) -> List[Dict[str, Any]]:
        """
        List all TA bundle versions for a request.

        Args:
            request_id: UUID of the request

        Returns:
            List of TA revision metadata

        Raises:
            StorageDownloadError: If listing fails
        """
        prefix = self._generate_storage_key("tas", str(request_id))

        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.config.bucket_tas, Prefix=prefix
            )

            revisions = []
            for obj in response.get("Contents", []):
                head = self.s3_client.head_object(
                    Bucket=self.config.bucket_tas, Key=obj["Key"]
                )

                revisions.append(
                    {
                        "storage_key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "metadata": head.get("Metadata", {}),
                    }
                )

            return revisions

        except Exception as e:
            raise StorageDownloadError(
                "Failed to list TA revisions",
                original_exception=e,
                context={"request_id": str(request_id)},
            )

    # ==================== Debug Bundle Operations ====================

    def upload_debug_bundle(
        self,
        validation_run_id: UUID,
        file_stream: BinaryIO,
        filename: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Upload debug bundle to storage.

        Args:
            validation_run_id: UUID of the validation run
            file_stream: Binary file stream
            filename: Bundle filename
            metadata: Additional metadata tags

        Returns:
            Storage key for the uploaded bundle

        Raises:
            StorageUploadError: If upload fails
        """
        safe_filename = sanitize_filename(filename)
        storage_key = self._generate_storage_key(
            "debug", str(validation_run_id), safe_filename
        )

        upload_metadata = metadata or {}
        upload_metadata.update(
            {
                "validation_run_id": str(validation_run_id),
                "upload_date": datetime.utcnow().isoformat(),
            }
        )

        try:
            logger.info(
                "uploading_debug_bundle",
                validation_run_id=str(validation_run_id),
                storage_key=storage_key,
            )

            self._stream_upload(
                bucket=self.config.bucket_debug,
                key=storage_key,
                file_stream=file_stream,
                content_type="application/zip",
                metadata=upload_metadata,
            )

            logger.info("debug_bundle_uploaded", storage_key=storage_key)
            return storage_key

        except Exception as e:
            logger.error("debug_bundle_upload_failed", error=str(e))
            raise StorageUploadError(
                "Failed to upload debug bundle",
                original_exception=e,
                context={"validation_run_id": str(validation_run_id)},
            )

    def download_debug_bundle(self, storage_key: str) -> bytes:
        """
        Download debug bundle from storage.

        Args:
            storage_key: Storage key of the bundle

        Returns:
            Bundle contents as bytes

        Raises:
            StorageNotFoundError: If bundle doesn't exist
            StorageDownloadError: If download fails
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.config.bucket_debug, Key=storage_key
            )
            return response["Body"].read()

        except ClientError as e:
            if e.response.get("Error", {}).get("Code", "") == "NoSuchKey":
                raise StorageNotFoundError(
                    "Debug bundle not found",
                    original_exception=e,
                    context={"storage_key": storage_key},
                )
            raise StorageDownloadError(
                "Failed to download debug bundle",
                original_exception=e,
                context={"storage_key": storage_key},
            )

    def get_debug_bundle_presigned_url(
        self, storage_key: str, expiration: Optional[int] = None
    ) -> str:
        """
        Generate presigned URL for debug bundle download.

        Args:
            storage_key: Storage key of the bundle
            expiration: URL expiration time in seconds

        Returns:
            Presigned URL

        Raises:
            StorageDownloadError: If URL generation fails
        """
        expiration = expiration or self.config.presigned_url_expiration

        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.config.bucket_debug, "Key": storage_key},
                ExpiresIn=expiration,
            )
            return url

        except Exception as e:
            raise StorageDownloadError(
                "Failed to generate presigned URL for debug bundle",
                original_exception=e,
                context={"storage_key": storage_key},
            )

    # ==================== Retention & Cleanup ====================

    def cleanup_expired_samples(self) -> int:
        """
        Delete log samples older than retention period.

        Returns:
            Number of samples deleted

        Raises:
            StorageRetentionError: If cleanup fails
        """
        if not self.config.retention_enabled:
            logger.info("retention_cleanup_disabled")
            return 0

        cutoff_date = parse_retention_date(self.config.retention_days)

        try:
            logger.info(
                "starting_retention_cleanup",
                cutoff_date=cutoff_date.isoformat(),
                retention_days=self.config.retention_days,
            )

            # List all objects in samples bucket
            response = self.s3_client.list_objects_v2(
                Bucket=self.config.bucket_samples
            )

            deleted_count = 0
            for obj in response.get("Contents", []):
                # Check if object is older than retention period
                if obj["LastModified"].replace(tzinfo=None) < cutoff_date:
                    self.s3_client.delete_object(
                        Bucket=self.config.bucket_samples, Key=obj["Key"]
                    )
                    deleted_count += 1
                    logger.info(
                        "expired_sample_deleted",
                        storage_key=obj["Key"],
                        last_modified=obj["LastModified"].isoformat(),
                    )

            logger.info(
                "retention_cleanup_completed",
                deleted_count=deleted_count,
            )
            return deleted_count

        except Exception as e:
            logger.error("retention_cleanup_failed", error=str(e))
            raise StorageRetentionError(
                "Failed to cleanup expired samples",
                original_exception=e,
                context={"cutoff_date": cutoff_date.isoformat()},
            )

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics for all buckets.

        Returns:
            Dictionary with statistics for each bucket

        Raises:
            StorageDownloadError: If stats retrieval fails
        """
        stats = {}

        buckets = {
            "samples": self.config.bucket_samples,
            "tas": self.config.bucket_tas,
            "debug": self.config.bucket_debug,
        }

        for bucket_type, bucket_name in buckets.items():
            try:
                response = self.s3_client.list_objects_v2(Bucket=bucket_name)

                objects = response.get("Contents", [])
                total_size = sum(obj["Size"] for obj in objects)
                total_count = len(objects)

                oldest = min(objects, key=lambda x: x["LastModified"], default=None)
                newest = max(objects, key=lambda x: x["LastModified"], default=None)

                stats[bucket_type] = {
                    "bucket_name": bucket_name,
                    "total_objects": total_count,
                    "total_size_bytes": total_size,
                    "total_size_formatted": format_storage_size(total_size),
                    "oldest_object": (
                        oldest["LastModified"].isoformat() if oldest else None
                    ),
                    "newest_object": (
                        newest["LastModified"].isoformat() if newest else None
                    ),
                }

            except Exception as e:
                logger.error(
                    "failed_to_get_bucket_stats",
                    bucket=bucket_name,
                    error=str(e),
                )
                stats[bucket_type] = {"error": str(e)}

        return stats

    # ==================== Utility Methods ====================

    def _generate_storage_key(self, bucket_type: str, *path_parts: str) -> str:
        """
        Generate consistent storage key from path components.

        Args:
            bucket_type: Type of bucket (samples, tas, debug)
            *path_parts: Path components to join

        Returns:
            Storage key
        """
        return "/".join(path_parts)

    def _stream_upload(
        self,
        bucket: str,
        key: str,
        file_stream: BinaryIO,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Upload file with streaming support and multipart for large files.

        Args:
            bucket: Target bucket name
            key: Storage key
            file_stream: Binary file stream
            content_type: MIME type
            metadata: Object metadata

        Raises:
            StorageUploadError: If upload fails
        """
        file_size = get_file_size(file_stream)
        threshold_bytes = self.config.multipart_threshold_mb * 1024 * 1024

        extra_args = {
            "ContentType": content_type,
            "Metadata": metadata or {},
        }

        try:
            if file_size > threshold_bytes:
                # Use multipart upload for large files
                logger.debug(
                    "using_multipart_upload",
                    file_size=format_storage_size(file_size),
                    threshold=f"{self.config.multipart_threshold_mb} MB",
                )

                # Reset stream position
                file_stream.seek(0)

                self.s3_client.upload_fileobj(
                    file_stream,
                    bucket,
                    key,
                    ExtraArgs=extra_args,
                    Config=boto3.s3.transfer.TransferConfig(
                        multipart_threshold=threshold_bytes,
                        multipart_chunksize=self.config.multipart_chunk_size_mb
                        * 1024
                        * 1024,
                    ),
                )
            else:
                # Simple upload for small files
                file_stream.seek(0)
                file_data = file_stream.read()

                self.s3_client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=file_data,
                    **extra_args,
                )

        except Exception as e:
            logger.error("stream_upload_failed", bucket=bucket, key=key, error=str(e))
            raise StorageUploadError(
                "Failed to upload file",
                original_exception=e,
                context={"bucket": bucket, "key": key},
            )
