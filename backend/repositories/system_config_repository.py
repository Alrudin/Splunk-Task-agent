"""
SystemConfigRepository for SystemConfig-specific database operations.
"""
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import SystemConfig
from backend.repositories.base import BaseRepository


class SystemConfigRepository(BaseRepository[SystemConfig]):
    """Repository for SystemConfig model with configuration-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SystemConfig)

    async def get_by_key(self, key: str) -> Optional[SystemConfig]:
        """Get configuration value by key."""
        result = await self.session.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        return result.scalar_one_or_none()

    async def get_value(self, key: str, default: Any = None) -> Any:
        """Get parsed value by key with default fallback."""
        config = await self.get_by_key(key)
        if not config:
            return default
        return self.parse_value(config)

    async def set_value(
        self,
        key: str,
        value: Any,
        value_type: str,
        updated_by: UUID,
        description: Optional[str] = None,
        is_secret: bool = False
    ) -> SystemConfig:
        """Create or update config entry."""
        # Convert value to string for storage
        if value_type == "json":
            value_str = json.dumps(value)
        elif value_type == "list":
            if isinstance(value, list):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
        else:
            value_str = str(value)

        # Check if config exists
        existing = await self.get_by_key(key)

        if existing:
            # Update existing
            await self.session.execute(
                update(SystemConfig)
                .where(SystemConfig.key == key)
                .values(
                    value=value_str,
                    value_type=value_type,
                    description=description or existing.description,
                    is_secret=is_secret,
                    updated_by=updated_by
                )
            )
            await self.session.flush()
            return await self.get_by_key(key)
        else:
            # Create new
            config = SystemConfig(
                key=key,
                value=value_str,
                value_type=value_type,
                description=description,
                is_secret=is_secret,
                updated_by=updated_by
            )
            self.session.add(config)
            await self.session.flush()
            await self.session.refresh(config)
            return config

    async def get_all_configs(self) -> Dict[str, Any]:
        """Get all configuration entries as dictionary."""
        result = await self.session.execute(select(SystemConfig))
        configs = result.scalars().all()
        return {config.key: self.parse_value(config) for config in configs}

    async def get_public_configs(self) -> Dict[str, Any]:
        """Get non-secret configurations for UI display."""
        result = await self.session.execute(
            select(SystemConfig).where(SystemConfig.is_secret == False)
        )
        configs = result.scalars().all()
        return {config.key: self.parse_value(config) for config in configs}

    async def delete_config(self, key: str) -> bool:
        """Delete configuration entry."""
        result = await self.session.execute(
            delete(SystemConfig).where(SystemConfig.key == key)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def get_configs_by_prefix(self, prefix: str) -> Dict[str, Any]:
        """Get all configs with keys starting with prefix."""
        result = await self.session.execute(
            select(SystemConfig).where(SystemConfig.key.like(f"{prefix}%"))
        )
        configs = result.scalars().all()
        return {config.key: self.parse_value(config) for config in configs}

    def parse_value(self, config: SystemConfig) -> Any:
        """
        Parse string value to appropriate Python type based on value_type.

        Args:
            config: SystemConfig instance

        Returns:
            Parsed value in appropriate Python type
        """
        value = config.value
        value_type = config.value_type

        if value_type == "string":
            return value
        elif value_type == "integer":
            try:
                return int(value)
            except ValueError:
                return None
        elif value_type == "boolean":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "json":
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        elif value_type == "list":
            try:
                # Try parsing as JSON first
                return json.loads(value)
            except json.JSONDecodeError:
                # Fall back to comma-separated
                return [item.strip() for item in value.split(",") if item.strip()]
        else:
            return value
