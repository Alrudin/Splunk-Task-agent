"""
Ollama LLM client for AI-assisted TA generation.

This module provides an async client for interacting with Ollama's OpenAI-compatible API.
It supports text completion, structured JSON responses, streaming, and health checks.
"""

import asyncio
import json
from typing import Any, AsyncIterator, Dict, Optional

import jsonschema
import structlog
from openai import AsyncOpenAI, OpenAIError, APITimeoutError, APIConnectionError

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


class OllamaClientError(Exception):
    """Base exception for Ollama client errors."""
    pass


class OllamaConnectionError(OllamaClientError):
    """Raised when connection to Ollama fails."""
    pass


class OllamaTimeoutError(OllamaClientError):
    """Raised when Ollama request times out."""
    pass


class OllamaGenerationError(OllamaClientError):
    """Raised when LLM generation fails."""
    pass


class OllamaResponseParseError(OllamaClientError):
    """Raised when JSON response parsing fails."""
    pass


class OllamaSchemaValidationError(OllamaClientError):
    """Raised when JSON response does not conform to expected schema."""

    def __init__(self, message: str, validation_errors: list):
        self.validation_errors = validation_errors
        super().__init__(message)


class OllamaClient:
    """
    Async client for Ollama LLM interactions.

    Uses OpenAI Python client configured for Ollama's OpenAI-compatible endpoint.
    Supports completion, structured responses, streaming, and health checks.

    Example:
        ```python
        client = OllamaClient()
        response = await client.generate_completion(
            prompt="Write a Splunk props.conf stanza",
            system_prompt="You are a Splunk configuration expert"
        )
        ```
    """

    def __init__(self):
        """Initialize Ollama client with settings."""
        self.settings = get_settings()
        self.logger = logger.bind(
            component="ollama_client",
            ollama_host=self.settings.ollama_host,
            ollama_port=self.settings.ollama_port,
            ollama_model=self.settings.ollama_model,
        )

        # Initialize OpenAI client with Ollama endpoint
        self.client = AsyncOpenAI(
            base_url=self.settings.ollama_base_url,
            api_key="ollama",  # Ollama doesn't require real API key
        )

        self.logger.info(
            "ollama_client_initialized",
            base_url=self.settings.ollama_base_url,
            model=self.settings.ollama_model,
            timeout=self.settings.ollama_timeout,
        )

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None,
    ) -> str:
        """
        Generate text completion using Ollama.

        Args:
            prompt: User prompt for generation
            system_prompt: Optional system prompt for role/context
            temperature: Optional temperature override (0.0-2.0)
            max_tokens: Optional max tokens override
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            Generated text completion

        Raises:
            OllamaConnectionError: If connection fails
            OllamaTimeoutError: If request times out
            OllamaGenerationError: If generation fails
        """
        correlation_id = id(prompt)
        temp = temperature if temperature is not None else self.settings.ollama_temperature
        max_tok = max_tokens if max_tokens is not None else self.settings.ollama_max_tokens

        # Truncate prompt for logging
        prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt

        self.logger.info(
            "generating_completion",
            correlation_id=correlation_id,
            prompt_preview=prompt_preview,
            temperature=temp,
            max_tokens=max_tok,
            has_system_prompt=system_prompt is not None,
            has_response_format=response_format is not None,
        )

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # Use asyncio.wait_for for timeout control
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.settings.ollama_model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=max_tok,
                    response_format=response_format,
                ),
                timeout=self.settings.ollama_timeout,
            )

            content = response.choices[0].message.content

            self.logger.info(
                "completion_generated",
                correlation_id=correlation_id,
                response_length=len(content),
                finish_reason=response.choices[0].finish_reason,
                usage=response.usage.model_dump() if response.usage else None,
            )

            return content

        except asyncio.TimeoutError as e:
            self.logger.error(
                "ollama_timeout",
                correlation_id=correlation_id,
                timeout=self.settings.ollama_timeout,
                error=str(e),
            )
            raise OllamaTimeoutError(
                f"Request timed out after {self.settings.ollama_timeout}s"
            ) from e

        except APIConnectionError as e:
            self.logger.error(
                "ollama_connection_error",
                correlation_id=correlation_id,
                base_url=self.settings.ollama_base_url,
                error=str(e),
            )
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {self.settings.ollama_base_url}: {e}"
            ) from e

        except APITimeoutError as e:
            self.logger.error(
                "ollama_api_timeout",
                correlation_id=correlation_id,
                error=str(e),
            )
            raise OllamaTimeoutError(f"Ollama API timeout: {e}") from e

        except OpenAIError as e:
            self.logger.error(
                "ollama_generation_error",
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise OllamaGenerationError(f"Generation failed: {e}") from e

    async def generate_structured_response(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate JSON response conforming to provided schema.

        Args:
            prompt: User prompt for generation
            system_prompt: System prompt with instructions
            response_schema: JSON schema for expected response structure

        Returns:
            Parsed and validated JSON response as dictionary

        Raises:
            OllamaResponseParseError: If JSON parsing fails
            OllamaSchemaValidationError: If response does not conform to schema
            OllamaGenerationError: If generation fails
        """
        correlation_id = id(prompt)

        self.logger.info(
            "generating_structured_response",
            correlation_id=correlation_id,
            schema_keys=list(response_schema.keys()) if response_schema else [],
        )

        # Request JSON format
        response_format = {"type": "json_object"}

        try:
            content = await self.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                response_format=response_format,
            )

            # Parse JSON response
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as e:
                self.logger.error(
                    "json_parse_error",
                    correlation_id=correlation_id,
                    content_preview=content[:500],
                    error=str(e),
                )
                raise OllamaResponseParseError(
                    f"Failed to parse JSON response: {e}\nContent: {content[:500]}"
                ) from e

            # Validate against schema if provided
            if response_schema:
                try:
                    jsonschema.validate(instance=parsed, schema=response_schema)
                except jsonschema.ValidationError as e:
                    # Collect all validation errors
                    validator = jsonschema.Draft7Validator(response_schema)
                    errors = list(validator.iter_errors(parsed))
                    error_messages = [
                        f"- {err.json_path}: {err.message}" for err in errors
                    ]

                    self.logger.error(
                        "schema_validation_error",
                        correlation_id=correlation_id,
                        error_count=len(errors),
                        errors=error_messages[:10],  # Limit logged errors
                        response_keys=list(parsed.keys()) if isinstance(parsed, dict) else None,
                    )
                    raise OllamaSchemaValidationError(
                        f"Response does not conform to schema: {e.message}\n"
                        f"Validation errors:\n" + "\n".join(error_messages[:10]),
                        validation_errors=error_messages,
                    ) from e

            self.logger.info(
                "structured_response_parsed",
                correlation_id=correlation_id,
                response_keys=list(parsed.keys()) if isinstance(parsed, dict) else None,
                schema_validated=bool(response_schema),
            )

            return parsed

        except OllamaClientError:
            # Re-raise Ollama-specific errors
            raise
        except Exception as e:
            self.logger.error(
                "structured_response_error",
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise OllamaGenerationError(f"Structured response generation failed: {e}") from e

    async def generate_streaming(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Generate streaming response for long outputs.

        Args:
            prompt: User prompt for generation
            system_prompt: Optional system prompt

        Yields:
            Text chunks as they arrive

        Raises:
            OllamaGenerationError: If streaming fails
        """
        correlation_id = id(prompt)
        prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt

        self.logger.info(
            "starting_streaming_generation",
            correlation_id=correlation_id,
            prompt_preview=prompt_preview,
        )

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = await self.client.chat.completions.create(
                model=self.settings.ollama_model,
                messages=messages,
                temperature=self.settings.ollama_temperature,
                max_tokens=self.settings.ollama_max_tokens,
                stream=True,
            )

            chunk_count = 0
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    chunk_count += 1
                    yield chunk.choices[0].delta.content

            self.logger.info(
                "streaming_completed",
                correlation_id=correlation_id,
                chunk_count=chunk_count,
            )

        except OpenAIError as e:
            self.logger.error(
                "streaming_error",
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise OllamaGenerationError(f"Streaming generation failed: {e}") from e

    async def health_check(self) -> bool:
        """
        Check Ollama service availability.

        Returns:
            True if healthy, False otherwise
        """
        self.logger.info("performing_health_check")

        try:
            # Simple completion request
            await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.settings.ollama_model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5,
                ),
                timeout=10.0,  # Short timeout for health check
            )

            self.logger.info("health_check_passed")
            return True

        except Exception as e:
            self.logger.warning(
                "health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False
