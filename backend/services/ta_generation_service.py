"""
TA Generation Service for creating Splunk Technology Add-on packages.

This service handles the packaging logic for TAs:
- Creating proper TA directory structure
- Writing .conf files in Splunk format
- Generating metadata and documentation
- Creating .tgz archives for distribution

Example usage:
    ```python
    storage_client = ObjectStorageClient()
    ta_service = TAGenerationService(storage_client)

    package_path, checksum = await ta_service.create_ta_package(
        ta_name="TA-custom-logs",
        ta_config={
            "inputs_conf": {...},
            "props_conf": {...},
            "transforms_conf": {...},
            "cim_mappings": {...}
        }
    )
    ```
"""

import hashlib
import os
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from backend.integrations.object_storage_client import ObjectStorageClient

logger = structlog.get_logger(__name__)


class TAGenerationService:
    """
    Service for generating Splunk TA packages.

    Creates complete TA directory structures with all required configuration
    files, metadata, and documentation, then packages them as .tgz archives.
    """

    def __init__(self, storage_client: Optional[ObjectStorageClient] = None):
        """
        Initialize TAGenerationService.

        Args:
            storage_client: Optional ObjectStorageClient for file operations
        """
        self.storage_client = storage_client
        self.logger = logger.bind(component="ta_generation_service")
        self.logger.info("ta_generation_service_initialized")

    async def create_ta_package(
        self,
        ta_name: str,
        ta_config: Dict[str, Any],
    ) -> Tuple[str, str]:
        """
        Create a complete TA package from configuration.

        Args:
            ta_name: Name of the TA (e.g., "TA-custom-logs")
            ta_config: Dict containing inputs_conf, props_conf, transforms_conf, cim_mappings

        Returns:
            Tuple of (package_path, checksum)
        """
        self.logger.info("creating_ta_package", ta_name=ta_name)

        # Ensure TA name follows convention
        if not ta_name.startswith("TA-"):
            ta_name = f"TA-{ta_name}"

        # Sanitize TA name
        ta_name = self._sanitize_name(ta_name)

        # Create temporary directory for TA structure
        temp_dir = tempfile.mkdtemp(prefix="splunk_ta_")
        ta_dir = os.path.join(temp_dir, ta_name)

        try:
            # Create directory structure
            self._create_directory_structure(ta_dir)

            # Write configuration files
            self._write_inputs_conf(ta_dir, ta_config.get("inputs_conf", {}))
            self._write_props_conf(ta_dir, ta_config.get("props_conf", {}))
            self._write_transforms_conf(ta_dir, ta_config.get("transforms_conf", {}))

            # Write CIM mappings (eventtypes.conf, tags.conf)
            cim_mappings = ta_config.get("cim_mappings", {})
            self._write_eventtypes_conf(ta_dir, cim_mappings)
            self._write_tags_conf(ta_dir, cim_mappings)

            # Write metadata
            self._write_default_meta(ta_dir, ta_name)
            self._write_app_conf(ta_dir, ta_name, ta_config)

            # Write documentation
            self._write_readme(ta_dir, ta_name, ta_config)

            # Create tarball
            package_path = self._create_tarball(temp_dir, ta_name)

            # Calculate checksum
            checksum = self._calculate_checksum(package_path)

            self.logger.info(
                "ta_package_created",
                ta_name=ta_name,
                package_path=package_path,
                checksum=checksum,
            )

            return package_path, checksum

        except Exception as e:
            self.logger.error(
                "ta_package_creation_failed",
                ta_name=ta_name,
                error=str(e),
                exc_info=True,
            )
            # Cleanup on failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def _sanitize_name(self, name: str) -> str:
        """Sanitize TA name to be filesystem-safe."""
        # Replace spaces with hyphens, remove special chars
        sanitized = name.replace(" ", "-")
        sanitized = "".join(c for c in sanitized if c.isalnum() or c in "-_")
        return sanitized

    def _create_directory_structure(self, ta_dir: str) -> None:
        """Create the standard TA directory structure."""
        directories = [
            ta_dir,
            os.path.join(ta_dir, "default"),
            os.path.join(ta_dir, "metadata"),
            os.path.join(ta_dir, "bin"),
            os.path.join(ta_dir, "static"),
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

        self.logger.debug("directory_structure_created", ta_dir=ta_dir)

    def _write_conf_file(
        self,
        file_path: str,
        stanzas: List[Dict[str, Any]],
        header_comment: Optional[str] = None,
    ) -> None:
        """
        Write a Splunk .conf file from stanza definitions.

        Args:
            file_path: Path to write the file
            stanzas: List of stanza dicts with 'stanza_name' and 'settings'
            header_comment: Optional header comment for the file
        """
        lines = []

        # Add header comment
        if header_comment:
            lines.append(f"# {header_comment}")
        lines.append(f"# Generated by Splunk TA Generator")
        lines.append(f"# Generated at: {datetime.utcnow().isoformat()}")
        lines.append("")

        for stanza in stanzas:
            stanza_name = stanza.get("stanza_name", "default")
            lines.append(f"[{stanza_name}]")

            # Write settings
            settings = stanza.get("settings", {})
            if not settings:
                # Use stanza dict directly, excluding stanza_name
                settings = {k: v for k, v in stanza.items() if k != "stanza_name"}

            for key, value in settings.items():
                # Skip None values
                if value is None:
                    continue

                # Handle boolean values
                if isinstance(value, bool):
                    value = "true" if value else "false"

                # Handle list values (for transforms REPORT, etc.)
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)

                # Escape special characters in values
                value_str = str(value)
                lines.append(f"{key} = {value_str}")

            lines.append("")  # Blank line between stanzas

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self.logger.debug("conf_file_written", file_path=file_path)

    def _write_inputs_conf(self, ta_dir: str, inputs_conf: Dict[str, Any]) -> None:
        """Write inputs.conf file."""
        stanzas = inputs_conf.get("stanzas", [])
        if stanzas:
            self._write_conf_file(
                os.path.join(ta_dir, "default", "inputs.conf"),
                stanzas,
                header_comment="Input configuration for data collection",
            )

    def _write_props_conf(self, ta_dir: str, props_conf: Dict[str, Any]) -> None:
        """Write props.conf file."""
        stanzas = props_conf.get("stanzas", [])
        if stanzas:
            self._write_conf_file(
                os.path.join(ta_dir, "default", "props.conf"),
                stanzas,
                header_comment="Parsing configuration for data extraction",
            )

    def _write_transforms_conf(self, ta_dir: str, transforms_conf: Dict[str, Any]) -> None:
        """Write transforms.conf file."""
        stanzas = transforms_conf.get("stanzas", [])
        if stanzas:
            self._write_conf_file(
                os.path.join(ta_dir, "default", "transforms.conf"),
                stanzas,
                header_comment="Field extraction transforms",
            )

    def _write_eventtypes_conf(self, ta_dir: str, cim_mappings: Dict[str, Any]) -> None:
        """Write eventtypes.conf from CIM mappings."""
        eventtypes = cim_mappings.get("eventtypes", [])
        if eventtypes:
            stanzas = []
            for et in eventtypes:
                stanzas.append({
                    "stanza_name": et.get("name", "unknown"),
                    "settings": {
                        "search": et.get("search", ""),
                    }
                })
            self._write_conf_file(
                os.path.join(ta_dir, "default", "eventtypes.conf"),
                stanzas,
                header_comment="Event type definitions for CIM compliance",
            )

    def _write_tags_conf(self, ta_dir: str, cim_mappings: Dict[str, Any]) -> None:
        """Write tags.conf from CIM mappings."""
        tags = cim_mappings.get("tags", {})
        if tags:
            stanzas = []
            for eventtype_name, tag_list in tags.items():
                settings = {}
                if isinstance(tag_list, list):
                    for tag in tag_list:
                        settings[tag] = "enabled"
                elif isinstance(tag_list, dict):
                    settings = tag_list

                stanzas.append({
                    "stanza_name": f"eventtype={eventtype_name}",
                    "settings": settings,
                })
            self._write_conf_file(
                os.path.join(ta_dir, "default", "tags.conf"),
                stanzas,
                header_comment="Tag assignments for CIM data model compliance",
            )

    def _write_default_meta(self, ta_dir: str, ta_name: str) -> None:
        """Write default.meta file."""
        content = f"""# Application-level permissions

[]
access = read : [ * ], write : [ admin ]
export = system

[default]
export = system

[props]
export = system

[transforms]
export = system

[eventtypes]
export = system

[tags]
export = system
"""
        meta_path = os.path.join(ta_dir, "metadata", "default.meta")
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.debug("default_meta_written", path=meta_path)

    def _write_app_conf(self, ta_dir: str, ta_name: str, ta_config: Dict[str, Any]) -> None:
        """Write app.conf file."""
        version = ta_config.get("version", "1.0.0")
        description = ta_config.get("description", f"Technology Add-on for {ta_name}")

        content = f"""# Splunk app configuration file
# Generated by Splunk TA Generator
# Generated at: {datetime.utcnow().isoformat()}

[install]
is_configured = false
state = enabled
build = {int(datetime.utcnow().timestamp())}

[ui]
is_visible = false
label = {ta_name}

[launcher]
author = Splunk TA Generator
description = {description}
version = {version}

[package]
id = {ta_name.lower().replace('-', '_')}
"""
        app_conf_path = os.path.join(ta_dir, "default", "app.conf")
        with open(app_conf_path, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.debug("app_conf_written", path=app_conf_path)

    def _write_readme(self, ta_dir: str, ta_name: str, ta_config: Dict[str, Any]) -> None:
        """Write README.md documentation file."""
        inputs = ta_config.get("inputs_conf", {}).get("stanzas", [])
        props = ta_config.get("props_conf", {}).get("stanzas", [])
        transforms = ta_config.get("transforms_conf", {}).get("stanzas", [])
        cim = ta_config.get("cim_mappings", {})

        # Extract sourcetypes
        sourcetypes = []
        for stanza in props:
            name = stanza.get("stanza_name", "")
            if name and not name.startswith("source::"):
                sourcetypes.append(name)

        content = f"""# {ta_name}

## Overview

This Technology Add-on (TA) was automatically generated by the Splunk TA Generator.

**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

## Installation

1. Download the TA package (.tgz file)
2. Install via Splunk Web: Apps > Manage Apps > Install app from file
3. Or extract to `$SPLUNK_HOME/etc/apps/`
4. Restart Splunk

## Configuration

### Sourcetypes

This TA defines the following sourcetypes:

{chr(10).join(f'- `{st}`' for st in sourcetypes) if sourcetypes else '- No sourcetypes defined'}

### Inputs

{len(inputs)} input stanza(s) defined in `default/inputs.conf`

### Field Extractions

{len(transforms)} transform stanza(s) defined in `default/transforms.conf`

## CIM Compliance

"""
        data_models = cim.get("data_models", cim.get("applicable_data_models", []))
        if data_models:
            content += f"""This TA maps to the following CIM data models:

{chr(10).join(f'- {dm}' for dm in data_models)}

### Field Aliases

"""
            aliases = cim.get("field_aliases", {})
            if aliases:
                content += "| Original Field | CIM Field |\n|---------------|------------|\n"
                for orig, cim_field in aliases.items():
                    content += f"| {orig} | {cim_field} |\n"
            else:
                content += "No field aliases defined.\n"
        else:
            content += "No CIM data model mappings defined.\n"

        content += """

## Support

This TA was automatically generated. For issues or enhancements, please contact
your Splunk administrator or regenerate with updated requirements.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | """ + datetime.utcnow().strftime('%Y-%m-%d') + """ | Initial auto-generated release |
"""

        readme_path = os.path.join(ta_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.debug("readme_written", path=readme_path)

    def _create_tarball(self, temp_dir: str, ta_name: str) -> str:
        """
        Create a .tgz archive of the TA directory.

        Args:
            temp_dir: Temporary directory containing TA
            ta_name: Name of the TA directory

        Returns:
            Path to the created tarball
        """
        tarball_path = os.path.join(temp_dir, f"{ta_name}.tgz")
        ta_dir = os.path.join(temp_dir, ta_name)

        with tarfile.open(tarball_path, "w:gz", compresslevel=6) as tar:
            tar.add(ta_dir, arcname=ta_name)

        self.logger.debug(
            "tarball_created",
            path=tarball_path,
            size=os.path.getsize(tarball_path),
        )

        return tarball_path

    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    async def cleanup_temp_files(self, package_path: str) -> None:
        """
        Clean up temporary files after upload.

        Args:
            package_path: Path to the package file
        """
        try:
            temp_dir = os.path.dirname(package_path)
            if temp_dir and os.path.exists(temp_dir) and temp_dir.startswith(tempfile.gettempdir()):
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.logger.debug("temp_files_cleaned", temp_dir=temp_dir)
        except Exception as e:
            self.logger.warning(
                "temp_cleanup_failed",
                path=package_path,
                error=str(e),
            )

    async def validate_ta_structure(self, ta_dir: str) -> Dict[str, Any]:
        """
        Validate TA directory structure and configuration files.

        Args:
            ta_dir: Path to TA directory

        Returns:
            Dict with validation results
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "files_found": [],
        }

        # Check required directories
        required_dirs = ["default", "metadata"]
        for dir_name in required_dirs:
            dir_path = os.path.join(ta_dir, dir_name)
            if not os.path.isdir(dir_path):
                results["errors"].append(f"Missing required directory: {dir_name}")
                results["valid"] = False

        # Check for config files
        config_files = [
            ("default/app.conf", True),
            ("default/props.conf", False),
            ("default/transforms.conf", False),
            ("default/inputs.conf", False),
            ("metadata/default.meta", True),
        ]

        for file_path, required in config_files:
            full_path = os.path.join(ta_dir, file_path)
            if os.path.isfile(full_path):
                results["files_found"].append(file_path)
            elif required:
                results["errors"].append(f"Missing required file: {file_path}")
                results["valid"] = False

        # Validate conf file syntax
        for conf_file in results["files_found"]:
            if conf_file.endswith(".conf"):
                file_path = os.path.join(ta_dir, conf_file)
                syntax_errors = self._validate_conf_syntax(file_path)
                if syntax_errors:
                    results["warnings"].extend(syntax_errors)

        return results

    def _validate_conf_syntax(self, file_path: str) -> List[str]:
        """
        Basic syntax validation for .conf files.

        Args:
            file_path: Path to conf file

        Returns:
            List of syntax errors/warnings
        """
        errors = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            in_stanza = False
            for line_num, line in enumerate(lines, 1):
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Check stanza header
                if line.startswith("["):
                    if not line.endswith("]"):
                        errors.append(
                            f"{file_path}:{line_num}: Unclosed stanza bracket"
                        )
                    in_stanza = True
                    continue

                # Check key-value pairs
                if "=" not in line and in_stanza:
                    # Could be a continuation line, but flag as warning
                    if not line.startswith(" ") and not line.startswith("\t"):
                        errors.append(
                            f"{file_path}:{line_num}: Line doesn't contain '=' (possible syntax error)"
                        )

        except Exception as e:
            errors.append(f"{file_path}: Failed to read file: {e}")

        return errors
