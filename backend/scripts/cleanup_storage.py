"""
Storage Cleanup Script

Enforce retention policies and clean up orphaned files in object storage.

Usage:
    python -m backend.scripts.cleanup_storage cleanup samples
    python -m backend.scripts.cleanup_storage cleanup orphaned
    python -m backend.scripts.cleanup_storage cleanup all
    python -m backend.scripts.cleanup_storage cleanup all --dry-run
    python -m backend.scripts.cleanup_storage cleanup all --force

Scheduling:
    Add to crontab for automated cleanup:
    # Run daily at 2 AM
    0 2 * * * cd /app && python -m backend.scripts.cleanup_storage cleanup all
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import click
import structlog

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.integrations.object_storage_client import ObjectStorageClient, StorageConfig
from backend.integrations.storage_exceptions import StorageRetentionError
from backend.integrations.storage_utils import format_storage_size

logger = structlog.get_logger(__name__)


@click.group()
def cli():
    """Storage cleanup and maintenance utilities."""
    pass


@cli.command()
@click.argument("target", type=click.Choice(["samples", "orphaned", "all"]))
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview deletions without executing",
)
@click.option(
    "--force",
    is_flag=True,
    help="Skip confirmation prompts",
)
@click.option(
    "--report",
    type=click.Path(),
    help="Save detailed JSON report to file",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
def cleanup(
    target: str, dry_run: bool, force: bool, report: str, verbose: bool
) -> None:
    """
    Run storage cleanup operations.

    TARGET: What to clean up (samples, orphaned, all)
    """
    # Configure logging
    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
        )

    click.echo("=" * 70)
    click.echo("TA Generator - Storage Cleanup")
    click.echo("=" * 70)
    click.echo()

    if dry_run:
        click.echo("[DRY RUN MODE - No files will be deleted]")
        click.echo()

    try:
        # Load configuration and initialize client
        config = StorageConfig.from_env()
        client = ObjectStorageClient(config)

        cleanup_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "target": target,
            "operations": [],
        }

        # Execute cleanup operations
        if target in ["samples", "all"]:
            click.echo("Cleaning up expired log samples...")
            click.echo(f"  Retention enabled: {config.retention_enabled}")
            click.echo(f"  Retention period: {config.retention_days} days")
            click.echo()

            if not config.retention_enabled:
                click.echo("  ⚠ Retention cleanup is disabled in configuration")
                click.echo("  Skipping sample cleanup")
                click.echo()
            else:
                if not force and not dry_run:
                    click.confirm(
                        f"  Delete samples older than {config.retention_days} days?",
                        abort=True,
                    )

                if dry_run:
                    # Preview what would be deleted
                    samples_to_delete = _preview_expired_samples(client, config)
                    click.echo(f"  Would delete {len(samples_to_delete)} samples")

                    total_size = sum(s["size"] for s in samples_to_delete)
                    click.echo(f"  Would free {format_storage_size(total_size)}")

                    cleanup_results["operations"].append(
                        {
                            "operation": "cleanup_expired_samples",
                            "preview": True,
                            "count": len(samples_to_delete),
                            "size_bytes": total_size,
                            "samples": samples_to_delete,
                        }
                    )
                else:
                    # Execute cleanup
                    deleted_count = client.cleanup_expired_samples()
                    click.echo(f"  ✓ Deleted {deleted_count} expired samples")

                    cleanup_results["operations"].append(
                        {
                            "operation": "cleanup_expired_samples",
                            "deleted_count": deleted_count,
                        }
                    )

                click.echo()

        if target in ["orphaned", "all"]:
            click.echo("Cleaning up orphaned files...")
            click.echo("  (Files in storage without database references)")
            click.echo()

            # Note: This requires database access which may not be available in all contexts
            # For now, we'll show a placeholder
            click.echo("  ⚠ Database integration not yet implemented")
            click.echo("  Skipping orphaned file cleanup")
            click.echo()

            cleanup_results["operations"].append(
                {
                    "operation": "cleanup_orphaned_files",
                    "status": "not_implemented",
                    "message": "Requires database integration",
                }
            )

        # Display storage statistics
        click.echo("Current Storage Statistics:")
        click.echo("-" * 70)

        stats = client.get_storage_stats()
        for bucket_type, bucket_stats in stats.items():
            if "error" in bucket_stats:
                click.echo(f"  {bucket_type}: Error - {bucket_stats['error']}", err=True)
            else:
                click.echo(f"  {bucket_type}:")
                click.echo(f"    Bucket: {bucket_stats['bucket_name']}")
                click.echo(f"    Objects: {bucket_stats['total_objects']}")
                click.echo(f"    Total Size: {bucket_stats['total_size_formatted']}")
                if bucket_stats["oldest_object"]:
                    click.echo(f"    Oldest: {bucket_stats['oldest_object']}")
                if bucket_stats["newest_object"]:
                    click.echo(f"    Newest: {bucket_stats['newest_object']}")
                click.echo()

        cleanup_results["storage_stats"] = stats

        # Save report if requested
        if report:
            report_path = Path(report)
            with open(report_path, "w") as f:
                json.dump(cleanup_results, f, indent=2, default=str)
            click.echo(f"✓ Report saved to: {report_path}")
            click.echo()

        click.echo("=" * 70)
        click.echo("✓ Cleanup completed successfully")
        click.echo("=" * 70)

        sys.exit(0)

    except StorageRetentionError as e:
        click.echo()
        click.echo("=" * 70, err=True)
        click.echo("✗ Retention Cleanup Error", err=True)
        click.echo("=" * 70, err=True)
        click.echo(str(e), err=True)
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


def _preview_expired_samples(
    client: ObjectStorageClient, config: StorageConfig
) -> List[Dict]:
    """
    Preview log samples that would be deleted by retention cleanup.

    Args:
        client: Object storage client
        config: Storage configuration

    Returns:
        List of sample metadata that would be deleted
    """
    from backend.integrations.storage_utils import parse_retention_date

    cutoff_date = parse_retention_date(config.retention_days)

    try:
        samples_to_delete = []
        continuation_token = None

        # Iterate through all pages
        while True:
            # Build request parameters
            list_params = {"Bucket": config.bucket_samples}
            if continuation_token:
                list_params["ContinuationToken"] = continuation_token

            response = client.s3_client.list_objects_v2(**list_params)

            # Process objects in current page
            for obj in response.get("Contents", []):
                if obj["LastModified"].replace(tzinfo=None) < cutoff_date:
                    samples_to_delete.append(
                        {
                            "key": obj["Key"],
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"].isoformat(),
                        }
                    )

            # Check if there are more pages
            if response.get("IsTruncated", False):
                continuation_token = response.get("NextContinuationToken")
            else:
                break

        return samples_to_delete

    except Exception as e:
        logger.error("failed_to_preview_samples", error=str(e))
        return []


if __name__ == "__main__":
    cli()
