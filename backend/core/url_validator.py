"""
URL validation utility for enforcing whitelist/blacklist policies.

This module provides URL validation to control which external domains
can be accessed by the system, following the ALLOWED_WEB_DOMAINS and
BLOCKED_WEB_DOMAINS configuration settings.
"""

from typing import List
from urllib.parse import urlparse

import structlog

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


class URLValidationError(Exception):
    """Raised when URL validation fails due to domain restrictions."""

    def __init__(self, url: str, domain: str, reason: str):
        self.url = url
        self.domain = domain
        self.reason = reason
        super().__init__(f"URL validation failed for '{url}': {reason}")


class URLValidator:
    """
    Validator for URL domain whitelist/blacklist enforcement.

    Checks URLs against configured allowed and blocked domain lists.
    Blocked domains take precedence over allowed domains.

    Example:
        ```python
        validator = URLValidator()
        if validator.validate_url("https://docs.splunk.com/page"):
            # URL is allowed
            pass
        ```
    """

    def __init__(self):
        """Initialize URLValidator with settings."""
        self.settings = get_settings()
        self.allowed_domains = self.settings.allowed_domains_list
        self.blocked_domains = self.settings.blocked_domains_list
        self.logger = logger.bind(
            component="url_validator",
            allowed_count=len(self.allowed_domains),
            blocked_count=len(self.blocked_domains),
        )
        self.logger.info(
            "url_validator_initialized",
            allowed_domains=self.allowed_domains,
            blocked_domains=self.blocked_domains,
        )

    def is_domain_allowed(self, domain: str) -> bool:
        """
        Check if domain is in the allowed list.

        Supports subdomain matching - e.g., "docs.splunk.com" matches "splunk.com".

        Args:
            domain: Domain to check (will be normalized to lowercase)

        Returns:
            True if domain is allowed, False otherwise
        """
        normalized_domain = domain.lower().strip()

        # If no allowed domains configured, allow all (unless blocked)
        if not self.allowed_domains:
            return True

        # Check for exact or subdomain match
        for allowed in self.allowed_domains:
            if domain_matches(normalized_domain, allowed):
                return True

        return False

    def is_domain_blocked(self, domain: str) -> bool:
        """
        Check if domain is in the blocked list.

        Blocked domains take precedence over allowed domains.
        Supports subdomain matching.

        Args:
            domain: Domain to check (will be normalized to lowercase)

        Returns:
            True if domain is blocked, False otherwise
        """
        normalized_domain = domain.lower().strip()

        # Check for exact or subdomain match
        for blocked in self.blocked_domains:
            if domain_matches(normalized_domain, blocked):
                return True

        return False

    def validate_url(self, url: str) -> bool:
        """
        Validate URL against whitelist/blacklist policies.

        Checks:
        1. URL is parseable
        2. Domain is not in blocked list
        3. Domain is in allowed list (if whitelist is configured)

        Args:
            url: Full URL to validate

        Returns:
            True if URL is valid and allowed

        Raises:
            URLValidationError: If URL is blocked or not in allowed list
        """
        domain = self.extract_domain(url)

        self.logger.debug(
            "validating_url",
            url=url,
            domain=domain,
        )

        # Check blocked list first (takes precedence)
        if self.is_domain_blocked(domain):
            self.logger.warning(
                "url_blocked",
                url=url,
                domain=domain,
                reason="Domain is in blocked list",
            )
            raise URLValidationError(
                url=url,
                domain=domain,
                reason="Domain is in blocked list"
            )

        # Check allowed list
        if not self.is_domain_allowed(domain):
            self.logger.warning(
                "url_not_allowed",
                url=url,
                domain=domain,
                reason="Domain is not in allowed list",
            )
            raise URLValidationError(
                url=url,
                domain=domain,
                reason="Domain is not in allowed list"
            )

        self.logger.debug(
            "url_validated",
            url=url,
            domain=domain,
        )

        return True

    def extract_domain(self, url: str) -> str:
        """
        Extract and normalize domain from URL.

        Handles:
        - URLs with or without scheme
        - IP addresses
        - Port numbers (stripped)
        - Localhost

        Args:
            url: URL to extract domain from

        Returns:
            Normalized domain string (lowercase)
        """
        # Add scheme if missing for proper parsing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Strip port number if present
            if ":" in domain:
                domain = domain.split(":")[0]

            return domain

        except Exception as e:
            self.logger.error(
                "domain_extraction_failed",
                url=url,
                error=str(e),
            )
            return ""

    def validate_urls(self, urls: List[str]) -> List[str]:
        """
        Validate multiple URLs and return only valid ones.

        Invalid or blocked URLs are logged and skipped.

        Args:
            urls: List of URLs to validate

        Returns:
            List of valid URLs
        """
        valid_urls = []

        for url in urls:
            try:
                if self.validate_url(url):
                    valid_urls.append(url)
            except URLValidationError:
                # Already logged in validate_url
                pass
            except Exception as e:
                self.logger.warning(
                    "url_validation_error",
                    url=url,
                    error=str(e),
                )

        self.logger.info(
            "urls_validated",
            total=len(urls),
            valid=len(valid_urls),
            blocked=len(urls) - len(valid_urls),
        )

        return valid_urls


def domain_matches(domain: str, pattern: str) -> bool:
    """
    Check if domain matches pattern (exact or subdomain match).

    Args:
        domain: Domain to check (e.g., "docs.splunk.com")
        pattern: Pattern to match against (e.g., "splunk.com")

    Returns:
        True if domain matches pattern exactly or is a subdomain of pattern

    Examples:
        domain_matches("splunk.com", "splunk.com") -> True
        domain_matches("docs.splunk.com", "splunk.com") -> True
        domain_matches("notsplunk.com", "splunk.com") -> False
        domain_matches("splunk.com.evil.com", "splunk.com") -> False
    """
    domain = domain.lower().strip()
    pattern = pattern.lower().strip()

    # Exact match
    if domain == pattern:
        return True

    # Subdomain match - domain ends with .pattern
    if domain.endswith(f".{pattern}"):
        return True

    return False
