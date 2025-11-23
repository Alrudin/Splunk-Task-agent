"""
Validation service for orchestrating TA validation logic.

Provides high-level validation workflow methods including search execution,
field coverage analysis, and report generation.
"""
import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog

from backend.core.config import settings
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.integrations.splunk_sandbox_client import (
    SearchExecutionError,
    SplunkSandboxClient,
    TAInstallationError,
)
from backend.repositories.log_sample_repository import LogSampleRepository
from backend.repositories.ta_revision_repository import TARevisionRepository
from backend.repositories.validation_run_repository import ValidationRunRepository

logger = structlog.get_logger(__name__)


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DebugBundleError(Exception):
    """Raised when debug bundle creation fails."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationService:
    """
    Service for orchestrating TA validation workflows.

    Manages the complete validation lifecycle including sandbox creation,
    TA installation, log ingestion, search execution, and report generation.
    """

    def __init__(
        self,
        splunk_client: SplunkSandboxClient,
        storage_client: ObjectStorageClient,
        validation_repo: ValidationRunRepository,
        ta_revision_repo: TARevisionRepository,
        sample_repo: LogSampleRepository,
    ):
        """
        Initialize validation service with dependencies.

        Args:
            splunk_client: Splunk sandbox orchestration client
            storage_client: Object storage client for MinIO
            validation_repo: ValidationRun repository
            ta_revision_repo: TARevision repository
            sample_repo: LogSample repository
        """
        self.splunk_client = splunk_client
        self.storage_client = storage_client
        self.validation_repo = validation_repo
        self.ta_revision_repo = ta_revision_repo
        self.sample_repo = sample_repo
        self.index_name = settings.validation_index_name
        self.field_coverage_threshold = settings.validation_field_coverage_threshold

    async def validate_ta_revision(
        self,
        validation_run_id: UUID,
        ta_revision_id: UUID,
        request_id: UUID,
    ) -> Dict[str, Any]:
        """
        Orchestrate complete TA validation workflow.

        Args:
            validation_run_id: ValidationRun record ID
            ta_revision_id: TARevision record ID
            request_id: Request record ID

        Returns:
            Validation report dictionary

        Raises:
            ValidationError: On validation failure
        """
        log = logger.bind(
            validation_run_id=str(validation_run_id),
            ta_revision_id=str(ta_revision_id),
            request_id=str(request_id),
        )
        log.info("validate_ta_revision_started")

        temp_dir = None
        sandbox_info = None
        ta_name = None

        try:
            # Create temp directory for working files
            temp_dir = Path(tempfile.mkdtemp(prefix=f"validation-{validation_run_id}-"))
            log.info("temp_directory_created", path=str(temp_dir))

            # Fetch TA revision metadata
            ta_revision = await self.ta_revision_repo.get_by_id(ta_revision_id)
            if not ta_revision:
                raise ValidationError(f"TARevision {ta_revision_id} not found")

            # Download TA tarball from MinIO
            ta_path = temp_dir / "ta.tgz"
            await self._download_file(
                bucket=settings.minio_bucket_tas,
                key=ta_revision.storage_key,
                dest_path=ta_path,
            )
            log.info("ta_downloaded", storage_key=ta_revision.storage_key)

            # Download sample files
            samples = await self.sample_repo.get_active_samples(request_id)
            if not samples:
                raise ValidationError("No active samples found for request")

            sample_paths = []
            for sample in samples:
                sample_path = temp_dir / f"sample_{sample.id}.log"
                await self._download_file(
                    bucket=settings.minio_bucket_samples,
                    key=sample.storage_key,
                    dest_path=sample_path,
                )
                sample_paths.append({
                    "path": sample_path,
                    "sourcetype": sample.detected_sourcetype or ta_revision.sourcetype or "unknown",
                    "sample_id": str(sample.id),
                })
            log.info("samples_downloaded", count=len(sample_paths))

            # Create Splunk sandbox
            sandbox_info = await self.splunk_client.create_sandbox(
                validation_run_id=str(validation_run_id),
            )
            log.info("sandbox_created", container_id=sandbox_info["container_id"][:12])

            # Update validation run with container ID
            await self.validation_repo.start_validation(
                validation_id=validation_run_id,
                container_id=sandbox_info["container_id"],
            )

            # Wait for Splunk to be ready
            await self.splunk_client.wait_for_ready(
                container_id=sandbox_info["container_id"],
                management_port=sandbox_info["management_port"],
            )
            log.info("splunk_ready")

            # Install TA
            ta_name = await self.splunk_client.install_ta(
                container_id=sandbox_info["container_id"],
                ta_tarball_path=str(ta_path),
                management_port=sandbox_info["management_port"],
            )
            log.info("ta_installed", ta_name=ta_name)

            # Create test index
            await self.splunk_client.create_test_index(
                container_id=sandbox_info["container_id"],
                index_name=self.index_name,
                management_port=sandbox_info["management_port"],
            )
            log.info("test_index_created", index_name=self.index_name)

            # Ingest all samples
            total_events = 0
            for sample_info in sample_paths:
                events = await self.splunk_client.ingest_sample_file(
                    container_id=sandbox_info["container_id"],
                    index_name=self.index_name,
                    sourcetype=sample_info["sourcetype"],
                    file_path=str(sample_info["path"]),
                    management_port=sandbox_info["management_port"],
                )
                total_events += events
            log.info("samples_ingested", total_events=total_events)

            # Wait for indexing to complete
            final_count = await self.splunk_client.wait_for_indexing(
                container_id=sandbox_info["container_id"],
                index_name=self.index_name,
                management_port=sandbox_info["management_port"],
                expected_count=total_events,
                timeout=60,
            )
            log.info("indexing_complete", event_count=final_count)

            # Get expected fields from TA revision metadata
            expected_fields = self._get_expected_fields(ta_revision)

            # Execute validation searches
            search_results = await self.execute_validation_searches(
                container_id=sandbox_info["container_id"],
                index_name=self.index_name,
                sourcetype=sample_paths[0]["sourcetype"] if sample_paths else "unknown",
                expected_fields=expected_fields,
                management_port=sandbox_info["management_port"],
            )
            log.info("validation_searches_complete")

            # Analyze field coverage
            field_coverage = self.analyze_field_coverage(
                search_results=search_results,
                expected_fields=expected_fields,
            )
            log.info("field_coverage_analyzed", coverage=field_coverage.get("overall_coverage", 0))

            # Generate validation report
            validation_report = self.generate_validation_report(
                validation_results={
                    "total_events": final_count,
                    "ta_name": ta_name,
                    "index_name": self.index_name,
                },
                field_coverage=field_coverage,
                search_results=search_results,
            )
            log.info("validation_report_generated", status=validation_report["status"])

            # If failed, create debug bundle
            if validation_report["status"] == "FAILED":
                splunk_logs = await self.splunk_client.get_splunkd_logs(
                    container_id=sandbox_info["container_id"],
                )
                ta_logs = await self.splunk_client.get_ta_logs(
                    container_id=sandbox_info["container_id"],
                    ta_name=ta_name,
                )

                debug_bundle_key = await self.create_debug_bundle(
                    validation_run_id=validation_run_id,
                    request_id=request_id,
                    ta_path=str(ta_path),
                    ta_name=ta_name,
                    validation_report=validation_report,
                    splunk_logs=splunk_logs,
                    ta_logs=ta_logs,
                )
                validation_report["debug_bundle_key"] = debug_bundle_key
                log.info("debug_bundle_created", key=debug_bundle_key)

            return validation_report

        except TAInstallationError as e:
            log.error("ta_installation_failed", error=str(e))
            raise ValidationError(f"TA installation failed: {str(e)}", details=e.details)

        except SearchExecutionError as e:
            log.error("search_execution_failed", error=str(e))
            raise ValidationError(f"Search execution failed: {str(e)}", details=e.details)

        except Exception as e:
            log.error("validation_failed", error=str(e), error_type=type(e).__name__)
            raise ValidationError(f"Validation failed: {str(e)}")

        finally:
            # Cleanup sandbox
            if sandbox_info:
                try:
                    await self.splunk_client.cleanup_sandbox(
                        container_id=sandbox_info["container_id"],
                        remove_volumes=True,
                        force=True,
                    )
                    log.info("sandbox_cleaned_up")
                except Exception as e:
                    log.error("sandbox_cleanup_failed", error=str(e))

            # Cleanup temp directory
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    log.info("temp_directory_cleaned_up")
                except Exception as e:
                    log.error("temp_cleanup_failed", error=str(e))

    async def _download_file(
        self,
        bucket: str,
        key: str,
        dest_path: Path,
    ) -> None:
        """Download file from object storage to local path."""
        with open(dest_path, "wb") as f:
            async for chunk in self.storage_client.download_file_async(bucket, key):
                f.write(chunk)

    def _get_expected_fields(self, ta_revision) -> List[str]:
        """
        Extract expected fields from TA revision metadata.

        Args:
            ta_revision: TARevision record

        Returns:
            List of expected field names
        """
        # Default essential fields
        default_fields = ["_time", "host", "source", "sourcetype", "_raw"]

        # Try to get fields from TA metadata
        if hasattr(ta_revision, "expected_fields") and ta_revision.expected_fields:
            return list(set(default_fields + ta_revision.expected_fields))

        # Try to get from config_content JSON
        if hasattr(ta_revision, "config_content") and ta_revision.config_content:
            try:
                config = ta_revision.config_content
                if isinstance(config, str):
                    config = json.loads(config)

                # Extract fields from transforms.conf REPORT stanzas
                transforms = config.get("transforms", {})
                for stanza in transforms.values():
                    if "FIELDS" in stanza:
                        fields = stanza["FIELDS"].split(",")
                        default_fields.extend([f.strip() for f in fields])
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        return list(set(default_fields))

    async def execute_validation_searches(
        self,
        container_id: str,
        index_name: str,
        sourcetype: str,
        expected_fields: List[str],
        management_port: int,
    ) -> Dict[str, Any]:
        """
        Execute validation searches and return results.

        Args:
            container_id: Docker container ID
            index_name: Index to search
            sourcetype: Sourcetype to search
            expected_fields: Expected fields to check
            management_port: Splunk management port

        Returns:
            Dictionary with search results for each check
        """
        log = logger.bind(
            container_id=container_id[:12],
            index_name=index_name,
            sourcetype=sourcetype,
        )

        results = {
            "ingestion_check": {},
            "timestamp_check": {},
            "field_extraction_check": {},
            "sample_events": [],
        }

        # 1. Basic ingestion check
        try:
            ingestion_query = f"search index={index_name} | stats count"
            ingestion_results = await self.splunk_client.execute_search(
                container_id=container_id,
                search_query=ingestion_query,
                management_port=management_port,
            )
            count = int(ingestion_results[0]["count"]) if ingestion_results else 0
            results["ingestion_check"] = {
                "passed": count > 0,
                "event_count": count,
                "query": ingestion_query,
            }
        except Exception as e:
            log.error("ingestion_check_failed", error=str(e))
            results["ingestion_check"] = {"passed": False, "error": str(e)}

        # 2. Timestamp parsing check
        try:
            timestamp_query = f"search index={index_name} | head 10 | eval has_time=if(_time>0, 1, 0) | stats sum(has_time) as valid_times, count"
            timestamp_results = await self.splunk_client.execute_search(
                container_id=container_id,
                search_query=timestamp_query,
                management_port=management_port,
            )
            if timestamp_results:
                valid_times = int(timestamp_results[0].get("valid_times", 0))
                total = int(timestamp_results[0].get("count", 0))
                results["timestamp_check"] = {
                    "passed": valid_times > 0 and valid_times == total,
                    "valid_timestamps": valid_times,
                    "total_checked": total,
                    "query": timestamp_query,
                }
            else:
                results["timestamp_check"] = {"passed": False, "error": "No results"}
        except Exception as e:
            log.error("timestamp_check_failed", error=str(e))
            results["timestamp_check"] = {"passed": False, "error": str(e)}

        # 3. Field extraction check for each expected field
        field_results = {}
        for field in expected_fields:
            if field.startswith("_"):  # Skip internal fields
                continue
            try:
                field_query = f'search index={index_name} | head 100 | stats count(eval(isnotnull({field}))) as present, count as total, values({field}) as sample_values'
                field_result = await self.splunk_client.execute_search(
                    container_id=container_id,
                    search_query=field_query,
                    management_port=management_port,
                )
                if field_result:
                    present = int(field_result[0].get("present", 0))
                    total = int(field_result[0].get("total", 0))
                    sample_values = field_result[0].get("sample_values", [])
                    if isinstance(sample_values, str):
                        sample_values = [sample_values]
                    field_results[field] = {
                        "extracted": present > 0,
                        "coverage_pct": (present / total * 100) if total > 0 else 0,
                        "present": present,
                        "total": total,
                        "sample_values": sample_values[:5],  # Limit to 5 samples
                    }
                else:
                    field_results[field] = {"extracted": False, "error": "No results"}
            except Exception as e:
                log.error("field_check_failed", field=field, error=str(e))
                field_results[field] = {"extracted": False, "error": str(e)}

        results["field_extraction_check"] = field_results

        # 4. Get sample events for report
        try:
            sample_query = f"search index={index_name} | head 5"
            sample_results = await self.splunk_client.execute_search(
                container_id=container_id,
                search_query=sample_query,
                management_port=management_port,
            )
            results["sample_events"] = sample_results[:5] if sample_results else []
        except Exception as e:
            log.error("sample_events_fetch_failed", error=str(e))
            results["sample_events"] = []

        return results

    def analyze_field_coverage(
        self,
        search_results: Dict[str, Any],
        expected_fields: List[str],
    ) -> Dict[str, Any]:
        """
        Analyze field coverage from search results.

        Args:
            search_results: Results from execute_validation_searches
            expected_fields: List of expected field names

        Returns:
            Field coverage analysis dictionary
        """
        field_check = search_results.get("field_extraction_check", {})

        extracted_count = 0
        total_expected = 0
        field_details = {}

        for field in expected_fields:
            if field.startswith("_"):  # Skip internal fields
                continue

            total_expected += 1
            field_info = field_check.get(field, {})

            if field_info.get("extracted", False):
                extracted_count += 1
                field_details[field] = {
                    "status": "extracted",
                    "coverage_pct": field_info.get("coverage_pct", 0),
                    "sample_values": field_info.get("sample_values", []),
                }
            else:
                field_details[field] = {
                    "status": "missing",
                    "error": field_info.get("error", "Not found in events"),
                }

        overall_coverage = (extracted_count / total_expected * 100) if total_expected > 0 else 0

        return {
            "overall_coverage": round(overall_coverage, 2),
            "fields_extracted": extracted_count,
            "fields_expected": total_expected,
            "fields": field_details,
            "meets_threshold": overall_coverage >= (self.field_coverage_threshold * 100),
        }

    def generate_validation_report(
        self,
        validation_results: Dict[str, Any],
        field_coverage: Dict[str, Any],
        search_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate comprehensive validation report.

        Args:
            validation_results: Basic validation results (event count, etc.)
            field_coverage: Field coverage analysis
            search_results: Raw search results

        Returns:
            Complete validation report dictionary
        """
        checks = []
        errors = []
        warnings = []

        # Ingestion check
        ingestion = search_results.get("ingestion_check", {})
        ingestion_passed = ingestion.get("passed", False)
        checks.append({
            "name": "ingestion",
            "passed": ingestion_passed,
            "details": f"Event count: {ingestion.get('event_count', 0)}",
        })
        if not ingestion_passed:
            errors.append("No events were indexed. Check sourcetype configuration.")

        # Timestamp check
        timestamp = search_results.get("timestamp_check", {})
        timestamp_passed = timestamp.get("passed", False)
        checks.append({
            "name": "timestamp_parsing",
            "passed": timestamp_passed,
            "details": f"Valid timestamps: {timestamp.get('valid_timestamps', 0)}/{timestamp.get('total_checked', 0)}",
        })
        if not timestamp_passed:
            errors.append("Timestamp parsing failed. Check TIME_FORMAT in props.conf.")

        # Field extraction check
        field_extraction_passed = field_coverage.get("meets_threshold", False)
        checks.append({
            "name": "field_extraction",
            "passed": field_extraction_passed,
            "details": f"Field coverage: {field_coverage.get('overall_coverage', 0)}% ({field_coverage.get('fields_extracted', 0)}/{field_coverage.get('fields_expected', 0)} fields)",
        })
        if not field_extraction_passed:
            missing_fields = [
                f for f, info in field_coverage.get("fields", {}).items()
                if info.get("status") == "missing"
            ]
            if missing_fields:
                errors.append(f"Missing fields: {', '.join(missing_fields[:10])}")

        # Determine overall status
        critical_checks_passed = ingestion_passed and timestamp_passed
        overall_passed = critical_checks_passed and field_extraction_passed

        # Add warnings for non-critical issues
        if ingestion_passed and not timestamp_passed:
            warnings.append("Events ingested but timestamps may not parse correctly.")

        if field_coverage.get("overall_coverage", 0) < 50:
            warnings.append("Field coverage is very low. Consider reviewing field extractions.")

        return {
            "status": "PASSED" if overall_passed else "FAILED",
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_events": validation_results.get("total_events", 0),
                "ta_name": validation_results.get("ta_name", "unknown"),
                "index_name": validation_results.get("index_name", self.index_name),
                "fields_extracted": field_coverage.get("fields_extracted", 0),
                "fields_expected": field_coverage.get("fields_expected", 0),
                "coverage_pct": field_coverage.get("overall_coverage", 0),
            },
            "field_coverage": field_coverage,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "sample_events": search_results.get("sample_events", [])[:3],
        }

    async def create_debug_bundle(
        self,
        validation_run_id: UUID,
        request_id: UUID,
        ta_path: str,
        ta_name: str,
        validation_report: Dict[str, Any],
        splunk_logs: str,
        ta_logs: str,
    ) -> str:
        """
        Create debug bundle with all validation artifacts.

        Args:
            validation_run_id: ValidationRun record ID
            request_id: Request record ID
            ta_path: Path to TA tarball
            ta_name: Name of the TA
            validation_report: Validation report dictionary
            splunk_logs: Splunk daemon logs
            ta_logs: TA-specific logs

        Returns:
            Storage key for the uploaded debug bundle

        Raises:
            DebugBundleError: On bundle creation failure
        """
        log = logger.bind(
            validation_run_id=str(validation_run_id),
            request_id=str(request_id),
        )
        log.info("create_debug_bundle_started")

        temp_dir = None
        try:
            # Create temp directory for bundle contents
            temp_dir = Path(tempfile.mkdtemp(prefix=f"debug-{validation_run_id}-"))
            bundle_dir = temp_dir / f"debug-bundle-{validation_run_id}"
            bundle_dir.mkdir()

            # Copy TA tarball
            ta_dest = bundle_dir / "ta.tgz"
            shutil.copy(ta_path, ta_dest)

            # Write validation report
            report_path = bundle_dir / "validation_report.json"
            with open(report_path, "w") as f:
                json.dump(validation_report, f, indent=2, default=str)

            # Write error summary
            error_summary_path = bundle_dir / "error_summary.txt"
            with open(error_summary_path, "w") as f:
                f.write(f"Validation Debug Bundle\n")
                f.write(f"=" * 50 + "\n\n")
                f.write(f"Validation Run ID: {validation_run_id}\n")
                f.write(f"Request ID: {request_id}\n")
                f.write(f"TA Name: {ta_name}\n")
                f.write(f"Status: {validation_report.get('status', 'UNKNOWN')}\n")
                f.write(f"Timestamp: {validation_report.get('timestamp', 'N/A')}\n\n")

                f.write("Errors:\n")
                for error in validation_report.get("errors", []):
                    f.write(f"  - {error}\n")
                f.write("\n")

                f.write("Warnings:\n")
                for warning in validation_report.get("warnings", []):
                    f.write(f"  - {warning}\n")
                f.write("\n")

                f.write("Checks:\n")
                for check in validation_report.get("checks", []):
                    status = "PASS" if check.get("passed") else "FAIL"
                    f.write(f"  [{status}] {check.get('name')}: {check.get('details')}\n")

            # Write Splunk logs
            if splunk_logs:
                logs_dir = bundle_dir / "logs"
                logs_dir.mkdir()
                splunkd_log_path = logs_dir / "splunkd.log"
                with open(splunkd_log_path, "w") as f:
                    f.write(splunk_logs)

                if ta_logs:
                    ta_log_path = logs_dir / f"{ta_name}.log"
                    with open(ta_log_path, "w") as f:
                        f.write(ta_logs)

            # Create zip archive
            zip_path = temp_dir / f"debug-{request_id}-{validation_run_id}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in bundle_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(bundle_dir)
                        zipf.write(file_path, arcname)

            # Upload to MinIO
            storage_key = f"debug/{request_id}/{validation_run_id}.zip"
            with open(zip_path, "rb") as f:
                await self.storage_client.upload_file_async(
                    file_obj=f,
                    bucket=settings.minio_bucket_debug,
                    key=storage_key,
                    content_type="application/zip",
                )

            log.info("create_debug_bundle_completed", storage_key=storage_key)
            return storage_key

        except Exception as e:
            log.error("create_debug_bundle_failed", error=str(e))
            raise DebugBundleError(f"Failed to create debug bundle: {str(e)}")

        finally:
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    log.warning("debug_bundle_cleanup_failed", error=str(e))
