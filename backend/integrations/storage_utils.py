"""
Object Storage Utility Functions

Helper functions for file validation, streaming, metadata construction,
and cleanup operations.
"""

import hashlib
import os
from datetime import datetime, timedelta
from io import SEEK_END, SEEK_SET
from typing import BinaryIO, Dict, Generator, List
from uuid import UUID


def validate_file_size(file_stream: BinaryIO, max_size_mb: int) -> bool:
    """
    Check if file size is within limits.

    Args:
        file_stream: Binary file stream
        max_size_mb: Maximum allowed size in megabytes

    Returns:
        True if file is within size limit, False otherwise
    """
    # Save current position
    current_pos = file_stream.tell()

    # Seek to end to get file size
    file_stream.seek(0, SEEK_END)
    file_size_bytes = file_stream.tell()

    # Restore original position
    file_stream.seek(current_pos, SEEK_SET)

    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size_bytes <= max_size_bytes


def validate_file_type(filename: str, allowed_extensions: List[str]) -> bool:
    """
    Validate file extension against allowed list.

    Args:
        filename: Name of the file
        allowed_extensions: List of allowed extensions (e.g., ['.log', '.txt', '.json'])

    Returns:
        True if file extension is allowed, False otherwise
    """
    if not filename:
        return False

    file_ext = os.path.splitext(filename)[1].lower()
    allowed_extensions_lower = [ext.lower() for ext in allowed_extensions]

    return file_ext in allowed_extensions_lower


def calculate_file_hash(file_stream: BinaryIO, algorithm: str = "sha256") -> str:
    """
    Generate cryptographic hash of file contents for deduplication.

    Args:
        file_stream: Binary file stream
        algorithm: Hash algorithm to use (default: sha256)

    Returns:
        Hexadecimal hash string
    """
    # Save current position
    current_pos = file_stream.tell()

    # Create hash object
    hash_obj = hashlib.new(algorithm)

    # Read file in chunks to avoid memory issues with large files
    file_stream.seek(0, SEEK_SET)
    for chunk in chunk_file_stream(file_stream, chunk_size=1048576):
        hash_obj.update(chunk)

    # Restore original position
    file_stream.seek(current_pos, SEEK_SET)

    return hash_obj.hexdigest()


def chunk_file_stream(
    file_stream: BinaryIO, chunk_size: int = 1048576
) -> Generator[bytes, None, None]:
    """
    Yield file chunks for streaming upload.

    Args:
        file_stream: Binary file stream
        chunk_size: Size of each chunk in bytes (default: 1MB)

    Yields:
        File chunks as bytes
    """
    while True:
        chunk = file_stream.read(chunk_size)
        if not chunk:
            break
        yield chunk


def estimate_upload_time(file_size: int, bandwidth_mbps: int = 100) -> float:
    """
    Estimate upload duration based on file size and bandwidth.

    Args:
        file_size: File size in bytes
        bandwidth_mbps: Available bandwidth in megabits per second

    Returns:
        Estimated upload time in seconds
    """
    # Convert bandwidth from Mbps to bytes per second
    bandwidth_bytes_per_sec = (bandwidth_mbps * 1000000) / 8

    # Calculate time with 20% overhead for protocol overhead
    estimated_time = (file_size / bandwidth_bytes_per_sec) * 1.2

    return estimated_time


def build_sample_metadata(
    request_id: UUID, filename: str, user_id: UUID, retention_enabled: bool
) -> Dict[str, str]:
    """
    Construct metadata dictionary for log samples.

    Args:
        request_id: UUID of the associated request
        filename: Original filename
        user_id: UUID of the user who uploaded the file
        retention_enabled: Whether retention policy is enabled

    Returns:
        Dictionary of metadata tags for S3 object
    """
    return {
        "request_id": str(request_id),
        "filename": filename,
        "user_id": str(user_id),
        "upload_date": datetime.utcnow().isoformat(),
        "retention_enabled": str(retention_enabled).lower(),
        "artifact_type": "log_sample",
    }


def build_ta_metadata(
    request_id: UUID, revision_id: UUID, version: int, generated_by: str
) -> Dict[str, str]:
    """
    Construct metadata dictionary for TA bundles.

    Args:
        request_id: UUID of the associated request
        revision_id: UUID of the TA revision
        version: Version number of the TA
        generated_by: Source of generation (e.g., 'AI', 'MANUAL')

    Returns:
        Dictionary of metadata tags for S3 object
    """
    return {
        "request_id": str(request_id),
        "revision_id": str(revision_id),
        "version": str(version),
        "generated_by": generated_by,
        "upload_date": datetime.utcnow().isoformat(),
        "artifact_type": "ta_bundle",
    }


def build_debug_metadata(
    validation_run_id: UUID, status: str, error_count: int
) -> Dict[str, str]:
    """
    Construct metadata dictionary for debug bundles.

    Args:
        validation_run_id: UUID of the validation run
        status: Status of the validation run (e.g., 'FAILED', 'ERROR')
        error_count: Number of errors encountered

    Returns:
        Dictionary of metadata tags for S3 object
    """
    return {
        "validation_run_id": str(validation_run_id),
        "status": status,
        "error_count": str(error_count),
        "upload_date": datetime.utcnow().isoformat(),
        "artifact_type": "debug_bundle",
    }


def parse_retention_date(retention_days: int) -> datetime:
    """
    Calculate cutoff date for retention cleanup.

    Args:
        retention_days: Number of days to retain files

    Returns:
        Datetime representing the cutoff date (UTC)
    """
    return datetime.utcnow() - timedelta(days=retention_days)


def format_storage_size(size_bytes: int) -> str:
    """
    Format byte size to human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 GB", "256 MB")
    """
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    return f"{size:.2f} {units[unit_index]}"


def get_file_size(file_stream: BinaryIO) -> int:
    """
    Get file size in bytes without modifying stream position.

    Args:
        file_stream: Binary file stream

    Returns:
        File size in bytes
    """
    current_pos = file_stream.tell()
    file_stream.seek(0, SEEK_END)
    file_size = file_stream.tell()
    file_stream.seek(current_pos, SEEK_SET)
    return file_size


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Replace problematic characters
    invalid_chars = '<>:"|?*\\'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        name = name[: max_length - len(ext)]
        filename = name + ext

    return filename
