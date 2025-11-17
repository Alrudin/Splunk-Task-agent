"""
Storage Initialization Script

Initialize MinIO/S3 buckets and verify connectivity for the TA Generator system.

Usage:
    python -m backend.scripts.init_storage
    python -m backend.scripts.init_storage --force
    python -m backend.scripts.init_storage --verify-only
    python -m backend.scripts.init_storage --verbose
"""

import sys
from pathlib import Path

import click
import structlog

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.integrations.object_storage_client import ObjectStorageClient, StorageConfig
from backend.integrations.storage_exceptions import (
    StorageBucketError,
    StorageConnectionError,
)

logger = structlog.get_logger(__name__)


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="Force recreate buckets if they already exist",
)
@click.option(
    "--verify-only",
    is_flag=True,
    help="Only verify connectivity without creating buckets",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
def init_storage(force: bool, verify_only: bool, verbose: bool) -> None:
    """
    Initialize object storage buckets and verify connectivity.

    This script creates the required S3/MinIO buckets for storing:
    - Log samples (uploaded by requestors)
    - TA bundles (generated artifacts)
    - Debug bundles (validation failure diagnostics)
    """
    # Configure logging
    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging_level=10)
        )

    click.echo("=" * 70)
    click.echo("TA Generator - Object Storage Initialization")
    click.echo("=" * 70)
    click.echo()

    try:
        # Load configuration
        click.echo("Loading configuration from environment...")
        config = StorageConfig.from_env()

        click.echo(f"  Endpoint: {config.endpoint}")
        click.echo(f"  Region: {config.region}")
        click.echo(f"  SSL: {config.use_ssl}")
        click.echo()

        # Initialize client
        click.echo("Initializing storage client...")
        client = ObjectStorageClient(config)
        click.echo("  ✓ Client initialized successfully")
        click.echo()

        if verify_only:
            # Verify connectivity only
            click.echo("Verifying bucket access...")
            buckets = {
                "Log Samples": config.bucket_samples,
                "TA Artifacts": config.bucket_tas,
                "Debug Bundles": config.bucket_debug,
            }

            all_accessible = True
            for bucket_type, bucket_name in buckets.items():
                try:
                    client.s3_client.head_bucket(Bucket=bucket_name)
                    click.echo(f"  ✓ {bucket_type}: {bucket_name} - accessible")
                except Exception as e:
                    click.echo(
                        f"  ✗ {bucket_type}: {bucket_name} - not accessible ({str(e)})",
                        err=True,
                    )
                    all_accessible = False

            click.echo()
            if all_accessible:
                click.echo("✓ All buckets are accessible")
                sys.exit(0)
            else:
                click.echo("✗ Some buckets are not accessible", err=True)
                sys.exit(1)

        # Create buckets
        click.echo("Creating storage buckets...")

        if force:
            click.echo("  (Force mode: will recreate existing buckets)")
            click.echo()

            # Delete existing buckets first
            buckets_to_delete = [
                config.bucket_samples,
                config.bucket_tas,
                config.bucket_debug,
            ]

            for bucket_name in buckets_to_delete:
                try:
                    # Delete all objects first
                    response = client.s3_client.list_objects_v2(Bucket=bucket_name)
                    for obj in response.get("Contents", []):
                        client.s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])

                    # Delete bucket
                    client.s3_client.delete_bucket(Bucket=bucket_name)
                    click.echo(f"  Deleted existing bucket: {bucket_name}")
                except Exception:
                    # Bucket might not exist, ignore
                    pass

        results = client.initialize_buckets()

        click.echo()
        click.echo("Bucket Creation Results:")
        click.echo("-" * 70)

        bucket_names = {
            config.bucket_samples: "Log Samples",
            config.bucket_tas: "TA Artifacts",
            config.bucket_debug: "Debug Bundles",
        }

        for bucket_name, created in results.items():
            bucket_type = bucket_names.get(bucket_name, "Unknown")
            status = "created" if created else "already exists"
            symbol = "+" if created else "•"
            click.echo(f"  {symbol} {bucket_type}: {bucket_name} ({status})")

        click.echo()
        click.echo("=" * 70)
        click.echo("✓ Storage initialization completed successfully")
        click.echo("=" * 70)
        click.echo()
        click.echo("Configuration Summary:")
        click.echo(f"  Retention Enabled: {config.retention_enabled}")
        click.echo(f"  Retention Days: {config.retention_days}")
        click.echo(f"  Max Upload Size: {config.max_upload_size_mb} MB")
        click.echo(f"  Presigned URL Expiration: {config.presigned_url_expiration}s")
        click.echo()

        sys.exit(0)

    except StorageConnectionError as e:
        click.echo()
        click.echo("=" * 70, err=True)
        click.echo("✗ Connection Error", err=True)
        click.echo("=" * 70, err=True)
        click.echo(str(e), err=True)
        click.echo()
        click.echo("Troubleshooting:", err=True)
        click.echo("  1. Ensure MinIO/S3 service is running", err=True)
        click.echo("  2. Check docker-compose services:", err=True)
        click.echo("       docker-compose ps", err=True)
        click.echo("  3. Verify MINIO_ENDPOINT in .env file", err=True)
        click.echo("  4. Check network connectivity to storage endpoint", err=True)
        click.echo()
        sys.exit(1)

    except StorageBucketError as e:
        click.echo()
        click.echo("=" * 70, err=True)
        click.echo("✗ Bucket Operation Error", err=True)
        click.echo("=" * 70, err=True)
        click.echo(str(e), err=True)
        click.echo()
        click.echo("Troubleshooting:", err=True)
        click.echo("  1. Verify MINIO_ACCESS_KEY and MINIO_SECRET_KEY", err=True)
        click.echo("  2. Check bucket permissions", err=True)
        click.echo("  3. Try --force flag to recreate buckets", err=True)
        click.echo()
        sys.exit(1)

    except ValueError as e:
        click.echo()
        click.echo("=" * 70, err=True)
        click.echo("✗ Configuration Error", err=True)
        click.echo("=" * 70, err=True)
        click.echo(str(e), err=True)
        click.echo()
        click.echo("Please ensure all required environment variables are set in .env file:", err=True)
        click.echo("  - MINIO_ENDPOINT", err=True)
        click.echo("  - MINIO_ACCESS_KEY", err=True)
        click.echo("  - MINIO_SECRET_KEY", err=True)
        click.echo("  - MINIO_BUCKET_SAMPLES", err=True)
        click.echo("  - MINIO_BUCKET_TAS", err=True)
        click.echo("  - MINIO_BUCKET_DEBUG", err=True)
        click.echo()
        sys.exit(1)

    except Exception as e:
        click.echo()
        click.echo("=" * 70, err=True)
        click.echo("✗ Unexpected Error", err=True)
        click.echo("=" * 70, err=True)
        click.echo(str(e), err=True)
        if verbose:
            import traceback
            click.echo()
            click.echo("Traceback:", err=True)
            click.echo(traceback.format_exc(), err=True)
        click.echo()
        sys.exit(1)


if __name__ == "__main__":
    init_storage()
