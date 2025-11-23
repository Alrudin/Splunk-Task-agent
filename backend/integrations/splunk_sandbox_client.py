"""
Splunk sandbox orchestration client for launching and managing ephemeral Splunk containers.

Provides async methods for creating, configuring, and managing Splunk Enterprise
containers for TA validation using Docker SDK.
"""
import asyncio
import random
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docker
import httpx
import structlog
from docker.errors import APIError, ContainerError, ImageNotFound, NotFound

from backend.core.config import settings

logger = structlog.get_logger(__name__)


# Custom Exceptions
class SandboxCreationError(Exception):
    """Raised when sandbox container creation fails."""

    def __init__(self, message: str, container_id: Optional[str] = None, details: Optional[Dict] = None):
        self.message = message
        self.container_id = container_id
        self.details = details or {}
        super().__init__(self.message)


class SandboxTimeoutError(Exception):
    """Raised when sandbox operations timeout."""

    def __init__(self, message: str, timeout: int, operation: str):
        self.message = message
        self.timeout = timeout
        self.operation = operation
        super().__init__(self.message)


class TAInstallationError(Exception):
    """Raised when TA installation fails."""

    def __init__(self, message: str, ta_name: Optional[str] = None, details: Optional[Dict] = None):
        self.message = message
        self.ta_name = ta_name
        self.details = details or {}
        super().__init__(self.message)


class SearchExecutionError(Exception):
    """Raised when search execution fails."""

    def __init__(self, message: str, search_query: Optional[str] = None, details: Optional[Dict] = None):
        self.message = message
        self.search_query = search_query
        self.details = details or {}
        super().__init__(self.message)


class SplunkSandboxClient:
    """
    Client for Splunk sandbox orchestration using Docker SDK.

    Manages ephemeral Splunk Enterprise containers for TA validation,
    including container lifecycle, TA installation, log ingestion, and search execution.
    """

    def __init__(self):
        """Initialize Splunk sandbox client with Docker SDK client."""
        self.docker_client = docker.from_env()
        self.splunk_image = settings.splunk_image
        self.admin_password = settings.splunk_admin_password
        self.startup_timeout = settings.splunk_startup_timeout
        self.docker_network = settings.docker_network
        self.splunk_host = settings.splunk_host
        self.use_ssl = settings.splunk_use_ssl
        self.verify_ssl = settings.splunk_verify_ssl

        logger.info(
            "splunk_sandbox_client_initialized",
            splunk_image=self.splunk_image,
            docker_network=self.docker_network,
            splunk_host=self.splunk_host,
            use_ssl=self.use_ssl,
        )

    def _get_base_url(self, port: int) -> str:
        """
        Build the base URL for Splunk REST API.

        Args:
            port: The port number for the Splunk management API

        Returns:
            Base URL string (e.g., http://localhost:18089)
        """
        protocol = "https" if self.use_ssl else "http"
        return f"{protocol}://{self.splunk_host}:{port}"

    def _get_bound_port(self, container, internal_port: str) -> Optional[int]:
        """
        Get the host port bound to a container's internal port.

        Args:
            container: Docker container object
            internal_port: Internal port string (e.g., "8089/tcp")

        Returns:
            Host port number or None if not found
        """
        container.reload()  # Refresh container info
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        bindings = ports.get(internal_port)
        if bindings and len(bindings) > 0:
            return int(bindings[0].get("HostPort"))
        return None

    async def create_sandbox(
        self,
        validation_run_id: str,
        labels: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Launch a new Splunk Enterprise container for validation.

        Uses Docker's ephemeral port assignment to avoid port conflicts.
        The container exposes ports 8089 (management) and 8088 (HEC), and
        Docker assigns available host ports automatically.

        Args:
            validation_run_id: Unique identifier for this validation run
            labels: Optional additional labels for the container
            max_retries: Maximum retries on port conflict errors

        Returns:
            Dict with container_id, management_url, hec_url, management_port, hec_port

        Raises:
            SandboxCreationError: On container creation failure
        """
        log = logger.bind(validation_run_id=validation_run_id)
        log.info("create_sandbox_started")

        container_name = f"splunk-validation-{validation_run_id}"

        for attempt in range(max_retries):
            try:
                # Ensure image is available
                try:
                    self.docker_client.images.get(self.splunk_image)
                except ImageNotFound:
                    log.info("pulling_splunk_image", image=self.splunk_image)
                    self.docker_client.images.pull(self.splunk_image)

                # Container configuration
                container_labels = {
                    "splunk-ta-validation": "true",
                    "validation-run-id": validation_run_id,
                }
                if labels:
                    container_labels.update(labels)

                # Environment variables for Splunk container
                environment = {
                    "SPLUNK_START_ARGS": "--accept-license",
                    "SPLUNK_PASSWORD": self.admin_password,
                    "SPLUNK_HEC_TOKEN": f"validation-{validation_run_id}",
                }

                # Use Docker ephemeral port assignment (None = auto-assign)
                # This avoids port conflicts when running multiple validations
                ports = {
                    "8089/tcp": None,  # Management port - auto-assign
                    "8088/tcp": None,  # HEC port - auto-assign
                }

                # Create container
                container = self.docker_client.containers.create(
                    image=self.splunk_image,
                    name=container_name,
                    environment=environment,
                    ports=ports,
                    labels=container_labels,
                    detach=True,
                    remove=False,  # Don't auto-remove, we'll clean up manually
                )

                # Try to connect to network if it exists
                try:
                    network = self.docker_client.networks.get(self.docker_network)
                    network.connect(container)
                    log.info("container_connected_to_network", network=self.docker_network)
                except NotFound:
                    log.warning("docker_network_not_found", network=self.docker_network)

                # Start container
                container.start()

                # Get the actual assigned ports after container start
                management_port = self._get_bound_port(container, "8089/tcp")
                hec_port = self._get_bound_port(container, "8088/tcp")

                if not management_port or not hec_port:
                    raise SandboxCreationError(
                        "Failed to get assigned ports from container",
                        container_id=container.id,
                    )

                log.info(
                    "create_sandbox_completed",
                    container_id=container.id,
                    container_name=container_name,
                    management_port=management_port,
                    hec_port=hec_port,
                )

                return {
                    "container_id": container.id,
                    "container_name": container_name,
                    "management_url": self._get_base_url(management_port),
                    "hec_url": self._get_base_url(hec_port),
                    "management_port": management_port,
                    "hec_port": hec_port,
                }

            except APIError as e:
                # Check if it's a port conflict error
                if "port is already allocated" in str(e).lower() and attempt < max_retries - 1:
                    log.warning("port_conflict_retrying", attempt=attempt + 1, error=str(e))
                    await asyncio.sleep(1)
                    continue
                log.error("create_sandbox_failed", error=str(e))
                raise SandboxCreationError(
                    f"Failed to create Splunk container: {str(e)}",
                    details={"validation_run_id": validation_run_id, "error_type": type(e).__name__},
                ) from e
            except (ContainerError, ImageNotFound) as e:
                log.error("create_sandbox_failed", error=str(e))
                raise SandboxCreationError(
                    f"Failed to create Splunk container: {str(e)}",
                    details={"validation_run_id": validation_run_id, "error_type": type(e).__name__},
                ) from e

        raise SandboxCreationError(
            f"Failed to create container after {max_retries} attempts",
            details={"validation_run_id": validation_run_id},
        )

    async def wait_for_ready(
        self,
        container_id: str,
        management_port: int,
        timeout: Optional[int] = None,
    ) -> bool:
        """
        Wait for Splunk container to become ready by polling REST API.

        Args:
            container_id: Docker container ID
            management_port: Splunk management port
            timeout: Optional timeout in seconds (defaults to settings)

        Returns:
            True if container is ready

        Raises:
            SandboxTimeoutError: If container doesn't become ready within timeout
        """
        log = logger.bind(container_id=container_id[:12])
        timeout = timeout or self.startup_timeout
        poll_interval = 5
        elapsed = 0

        log.info("wait_for_ready_started", timeout=timeout)

        base_url = self._get_base_url(management_port)
        url = f"{base_url}/services/server/info"
        auth = ("admin", self.admin_password)

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=10.0) as client:
            while elapsed < timeout:
                try:
                    response = await client.get(url, auth=auth)
                    if response.status_code == 200:
                        log.info("splunk_container_ready", elapsed_seconds=elapsed)
                        return True
                except (httpx.RequestError, httpx.TimeoutException):
                    pass

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                # Check container is still running
                try:
                    container = self.docker_client.containers.get(container_id)
                    if container.status != "running":
                        log.error("container_stopped_unexpectedly", status=container.status)
                        raise SandboxCreationError(
                            f"Container stopped unexpectedly with status: {container.status}",
                            container_id=container_id,
                        )
                except NotFound:
                    raise SandboxCreationError(
                        "Container not found during startup",
                        container_id=container_id,
                    )

        raise SandboxTimeoutError(
            f"Splunk container did not become ready within {timeout} seconds",
            timeout=timeout,
            operation="wait_for_ready",
        )

    async def stop_sandbox(self, container_id: str, timeout: int = 30) -> None:
        """
        Gracefully stop a Splunk container.

        Args:
            container_id: Docker container ID
            timeout: Timeout for graceful stop in seconds
        """
        log = logger.bind(container_id=container_id[:12])
        log.info("stop_sandbox_started", timeout=timeout)

        try:
            container = self.docker_client.containers.get(container_id)
            container.stop(timeout=timeout)
            log.info("stop_sandbox_completed")
        except NotFound:
            log.warning("container_not_found_for_stop")
        except APIError as e:
            log.error("stop_sandbox_failed", error=str(e))
            raise

    async def cleanup_sandbox(
        self,
        container_id: str,
        remove_volumes: bool = True,
        force: bool = True,
    ) -> None:
        """
        Remove a Splunk container and optionally its volumes.

        Args:
            container_id: Docker container ID
            remove_volumes: Whether to remove associated volumes
            force: Force removal even if container is running
        """
        log = logger.bind(container_id=container_id[:12])
        log.info("cleanup_sandbox_started", remove_volumes=remove_volumes, force=force)

        try:
            container = self.docker_client.containers.get(container_id)
            container.remove(v=remove_volumes, force=force)
            log.info("cleanup_sandbox_completed")
        except NotFound:
            log.warning("container_not_found_for_cleanup")
        except APIError as e:
            log.error("cleanup_sandbox_failed", error=str(e))
            raise

    async def install_ta(
        self,
        container_id: str,
        ta_tarball_path: str,
        management_port: int,
    ) -> str:
        """
        Install a TA into the Splunk container.

        Args:
            container_id: Docker container ID
            ta_tarball_path: Path to TA .tgz file
            management_port: Splunk management port

        Returns:
            Name of the installed TA

        Raises:
            TAInstallationError: On installation failure
        """
        log = logger.bind(container_id=container_id[:12], ta_path=ta_tarball_path)
        log.info("install_ta_started")

        try:
            container = self.docker_client.containers.get(container_id)

            # Read and extract TA name from tarball
            with tarfile.open(ta_tarball_path, "r:gz") as tar:
                # Get TA name from top-level directory
                members = tar.getnames()
                if not members:
                    raise TAInstallationError("TA tarball is empty")

                ta_name = members[0].split("/")[0]
                log.info("ta_name_extracted", ta_name=ta_name)

            # Copy tarball to container
            with open(ta_tarball_path, "rb") as f:
                ta_data = f.read()

            # Create tar archive for put_archive
            tar_stream = BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                tarinfo = tarfile.TarInfo(name=f"{ta_name}.tgz")
                tarinfo.size = len(ta_data)
                tar.addfile(tarinfo, BytesIO(ta_data))
            tar_stream.seek(0)

            # Put archive in container's apps directory
            container.put_archive("/opt/splunk/etc/apps/", tar_stream)

            # Extract tarball in container
            exit_code, output = container.exec_run(
                f"tar -xzf /opt/splunk/etc/apps/{ta_name}.tgz -C /opt/splunk/etc/apps/",
                user="splunk",
            )
            if exit_code != 0:
                raise TAInstallationError(
                    f"Failed to extract TA: {output.decode()}",
                    ta_name=ta_name,
                )

            # Remove the tarball
            container.exec_run(f"rm /opt/splunk/etc/apps/{ta_name}.tgz", user="splunk")

            # Restart Splunk to load the TA
            log.info("restarting_splunk_after_ta_install")
            await self._restart_splunk(container_id, management_port)

            # Verify TA is installed
            if not await self.verify_ta_installed(container_id, ta_name, management_port):
                raise TAInstallationError(
                    f"TA '{ta_name}' not found after installation",
                    ta_name=ta_name,
                )

            log.info("install_ta_completed", ta_name=ta_name)
            return ta_name

        except NotFound as e:
            raise TAInstallationError(
                "Container not found",
                details={"container_id": container_id},
            ) from e
        except Exception as e:
            if isinstance(e, TAInstallationError):
                raise
            log.error("install_ta_failed", error=str(e))
            raise TAInstallationError(
                f"Failed to install TA: {str(e)}",
                details={"container_id": container_id, "ta_path": ta_tarball_path},
            ) from e

    async def _restart_splunk(self, container_id: str, management_port: int) -> None:
        """
        Restart Splunk service inside container and wait for it to come back.

        Args:
            container_id: Docker container ID
            management_port: Splunk management port
        """
        log = logger.bind(container_id=container_id[:12])

        # Restart via REST API
        base_url = self._get_base_url(management_port)
        url = f"{base_url}/services/server/control/restart"
        auth = ("admin", self.admin_password)

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
            try:
                await client.post(url, auth=auth)
            except httpx.RequestError:
                pass  # Restart causes connection drop, this is expected

        # Wait for Splunk to come back
        log.info("waiting_for_splunk_restart")
        await asyncio.sleep(10)  # Give it time to start restarting
        await self.wait_for_ready(container_id, management_port, timeout=120)

    async def verify_ta_installed(
        self,
        container_id: str,
        ta_name: str,
        management_port: int,
    ) -> bool:
        """
        Verify a TA is installed by checking REST API.

        Args:
            container_id: Docker container ID
            ta_name: Name of the TA to verify
            management_port: Splunk management port

        Returns:
            True if TA is installed
        """
        log = logger.bind(container_id=container_id[:12], ta_name=ta_name)

        base_url = self._get_base_url(management_port)
        url = f"{base_url}/services/apps/local/{ta_name}"
        auth = ("admin", self.admin_password)

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
            try:
                response = await client.get(url, auth=auth)
                if response.status_code == 200:
                    log.info("ta_verified_installed")
                    return True
                log.warning("ta_not_found", status_code=response.status_code)
                return False
            except httpx.RequestError as e:
                log.error("ta_verification_failed", error=str(e))
                return False

    async def create_test_index(
        self,
        container_id: str,
        index_name: str,
        management_port: int,
    ) -> bool:
        """
        Create a test index for validation.

        Args:
            container_id: Docker container ID
            index_name: Name of the index to create
            management_port: Splunk management port

        Returns:
            True if index was created successfully
        """
        log = logger.bind(container_id=container_id[:12], index_name=index_name)
        log.info("create_test_index_started")

        base_url = self._get_base_url(management_port)
        url = f"{base_url}/services/data/indexes"
        auth = ("admin", self.admin_password)
        data = {"name": index_name}

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
            try:
                response = await client.post(url, auth=auth, data=data)
                if response.status_code in (200, 201, 409):  # 409 = already exists
                    log.info("create_test_index_completed", status=response.status_code)
                    return True
                log.error("create_test_index_failed", status=response.status_code, body=response.text)
                return False
            except httpx.RequestError as e:
                log.error("create_test_index_request_failed", error=str(e))
                return False

    async def ingest_sample_file(
        self,
        container_id: str,
        index_name: str,
        sourcetype: str,
        file_path: str,
        management_port: int,
    ) -> int:
        """
        Ingest a sample file using Splunk's oneshot command.

        Args:
            container_id: Docker container ID
            index_name: Target index name
            sourcetype: Sourcetype for the data
            file_path: Path to the file to ingest
            management_port: Splunk management port

        Returns:
            Number of events ingested (estimated)

        Raises:
            SearchExecutionError: On ingestion failure
        """
        log = logger.bind(
            container_id=container_id[:12],
            index_name=index_name,
            sourcetype=sourcetype,
            file_path=file_path,
        )
        log.info("ingest_sample_file_started")

        try:
            container = self.docker_client.containers.get(container_id)

            # Copy file to container
            file_name = Path(file_path).name
            container_path = f"/tmp/{file_name}"

            with open(file_path, "rb") as f:
                file_data = f.read()

            # Create tar archive for put_archive
            tar_stream = BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                tarinfo = tarfile.TarInfo(name=file_name)
                tarinfo.size = len(file_data)
                tar.addfile(tarinfo, BytesIO(file_data))
            tar_stream.seek(0)

            container.put_archive("/tmp/", tar_stream)

            # Ingest using splunk add oneshot
            cmd = (
                f"/opt/splunk/bin/splunk add oneshot {container_path} "
                f"-index {index_name} -sourcetype {sourcetype} "
                f"-auth admin:{self.admin_password}"
            )
            exit_code, output = container.exec_run(cmd, user="splunk")

            if exit_code != 0:
                log.error("ingest_failed", exit_code=exit_code, output=output.decode())
                raise SearchExecutionError(
                    f"Failed to ingest file: {output.decode()}",
                    details={"file_path": file_path, "index": index_name},
                )

            # Wait for indexing
            await asyncio.sleep(5)

            # Get event count
            event_count = await self._get_event_count(container_id, index_name, management_port)

            log.info("ingest_sample_file_completed", event_count=event_count)
            return event_count

        except NotFound as e:
            raise SearchExecutionError(
                "Container not found",
                details={"container_id": container_id},
            ) from e

    async def _get_event_count(
        self,
        container_id: str,
        index_name: str,
        management_port: int,
    ) -> int:
        """Get the number of events in an index."""
        search_query = f"search index={index_name} | stats count"
        results = await self.execute_search(container_id, search_query, management_port)

        if results and len(results) > 0 and "count" in results[0]:
            return int(results[0]["count"])
        return 0

    async def wait_for_indexing(
        self,
        container_id: str,
        index_name: str,
        management_port: int,
        expected_count: Optional[int] = None,
        timeout: int = 60,
    ) -> int:
        """
        Wait for indexing to complete.

        Args:
            container_id: Docker container ID
            index_name: Index name to check
            management_port: Splunk management port
            expected_count: Optional expected event count
            timeout: Timeout in seconds

        Returns:
            Final event count
        """
        log = logger.bind(
            container_id=container_id[:12],
            index_name=index_name,
            expected_count=expected_count,
        )
        log.info("wait_for_indexing_started", timeout=timeout)

        elapsed = 0
        poll_interval = 5
        last_count = 0
        stable_iterations = 0

        while elapsed < timeout:
            count = await self._get_event_count(container_id, index_name, management_port)

            if expected_count and count >= expected_count:
                log.info("wait_for_indexing_completed", event_count=count)
                return count

            # If no expected count, wait for count to stabilize
            if count == last_count and count > 0:
                stable_iterations += 1
                if stable_iterations >= 2:
                    log.info("wait_for_indexing_completed", event_count=count)
                    return count
            else:
                stable_iterations = 0

            last_count = count
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        log.warning("wait_for_indexing_timeout", final_count=last_count)
        return last_count

    async def execute_search(
        self,
        container_id: str,
        search_query: str,
        management_port: int,
        max_results: int = 1000,
        timeout: int = 120,
    ) -> List[Dict[str, Any]]:
        """
        Execute a search and return results.

        Args:
            container_id: Docker container ID
            search_query: SPL search query
            management_port: Splunk management port
            max_results: Maximum number of results to return
            timeout: Search timeout in seconds

        Returns:
            List of result dictionaries

        Raises:
            SearchExecutionError: On search failure
        """
        log = logger.bind(container_id=container_id[:12], search_query=search_query[:100])
        log.info("execute_search_started")

        # Create search job
        base_url = self._get_base_url(management_port)
        url = f"{base_url}/services/search/jobs"
        auth = ("admin", self.admin_password)
        data = {
            "search": search_query,
            "output_mode": "json",
            "max_count": max_results,
        }

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
            try:
                # Create job
                response = await client.post(url, auth=auth, data=data)
                if response.status_code not in (200, 201):
                    raise SearchExecutionError(
                        f"Failed to create search job: {response.text}",
                        search_query=search_query,
                    )

                # Get job SID from response
                try:
                    job_response = response.json()
                    sid = job_response.get("sid")
                except Exception:
                    # Fallback: parse from XML-like response
                    import re

                    match = re.search(r"<sid>([^<]+)</sid>", response.text)
                    if match:
                        sid = match.group(1)
                    else:
                        raise SearchExecutionError(
                            f"Could not extract SID from response: {response.text}",
                            search_query=search_query,
                        )

                if not sid:
                    raise SearchExecutionError(
                        "No SID returned from search job creation",
                        search_query=search_query,
                    )

                # Poll for job completion
                job_url = f"{base_url}/services/search/jobs/{sid}"
                elapsed = 0
                poll_interval = 2

                while elapsed < timeout:
                    status_response = await client.get(
                        job_url, auth=auth, params={"output_mode": "json"}
                    )
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        entry = status_data.get("entry", [{}])[0]
                        content = entry.get("content", {})
                        dispatch_state = content.get("dispatchState", "")
                        is_done = content.get("isDone", False)

                        if is_done or dispatch_state == "DONE":
                            break

                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval

                # Get results
                results_url = f"{base_url}/services/search/jobs/{sid}/results"
                results_response = await client.get(
                    results_url, auth=auth, params={"output_mode": "json", "count": max_results}
                )

                if results_response.status_code != 200:
                    log.warning("search_results_not_available", status=results_response.status_code)
                    return []

                results_data = results_response.json()
                results = results_data.get("results", [])

                log.info("execute_search_completed", result_count=len(results))
                return results

            except httpx.RequestError as e:
                raise SearchExecutionError(
                    f"Search request failed: {str(e)}",
                    search_query=search_query,
                ) from e

    async def get_splunkd_logs(
        self,
        container_id: str,
        lines: int = 500,
    ) -> str:
        """
        Retrieve splunkd.log from container.

        Args:
            container_id: Docker container ID
            lines: Number of lines to retrieve

        Returns:
            Log content as string
        """
        log = logger.bind(container_id=container_id[:12])

        try:
            container = self.docker_client.containers.get(container_id)
            exit_code, output = container.exec_run(
                f"tail -n {lines} /opt/splunk/var/log/splunk/splunkd.log",
                user="splunk",
            )
            return output.decode("utf-8", errors="replace")
        except NotFound:
            log.warning("container_not_found_for_logs")
            return ""
        except Exception as e:
            log.error("get_splunkd_logs_failed", error=str(e))
            return ""

    async def get_ta_logs(
        self,
        container_id: str,
        ta_name: str,
        lines: int = 200,
    ) -> str:
        """
        Retrieve TA-specific logs from container.

        Args:
            container_id: Docker container ID
            ta_name: Name of the TA
            lines: Number of lines to retrieve

        Returns:
            Log content as string
        """
        log = logger.bind(container_id=container_id[:12], ta_name=ta_name)

        try:
            container = self.docker_client.containers.get(container_id)

            # Check for TA-specific log file
            log_path = f"/opt/splunk/var/log/splunk/{ta_name.lower()}.log"
            exit_code, output = container.exec_run(
                f"test -f {log_path} && tail -n {lines} {log_path}",
                user="splunk",
            )

            if exit_code == 0:
                return output.decode("utf-8", errors="replace")

            # Fallback: search for any logs mentioning the TA
            exit_code, output = container.exec_run(
                f"grep -h '{ta_name}' /opt/splunk/var/log/splunk/*.log | tail -n {lines}",
                user="splunk",
            )
            return output.decode("utf-8", errors="replace")

        except NotFound:
            log.warning("container_not_found_for_ta_logs")
            return ""
        except Exception as e:
            log.error("get_ta_logs_failed", error=str(e))
            return ""

    async def get_metrics_log(
        self,
        container_id: str,
        lines: int = 200,
    ) -> str:
        """
        Retrieve metrics.log from container.

        Args:
            container_id: Docker container ID
            lines: Number of lines to retrieve

        Returns:
            Log content as string
        """
        log = logger.bind(container_id=container_id[:12])

        try:
            container = self.docker_client.containers.get(container_id)
            exit_code, output = container.exec_run(
                f"tail -n {lines} /opt/splunk/var/log/splunk/metrics.log",
                user="splunk",
            )
            return output.decode("utf-8", errors="replace")
        except NotFound:
            log.warning("container_not_found_for_metrics")
            return ""
        except Exception as e:
            log.error("get_metrics_log_failed", error=str(e))
            return ""

    async def get_container_status(self, container_id: str) -> Optional[str]:
        """
        Get the current status of a container.

        Args:
            container_id: Docker container ID

        Returns:
            Container status string or None if not found
        """
        try:
            container = self.docker_client.containers.get(container_id)
            return container.status
        except NotFound:
            return None
