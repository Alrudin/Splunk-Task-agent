"""
Prompt builder service for constructing context-rich prompts for TA generation.

This service assembles prompts using request metadata, log samples, and RAG context
retrieved from Pinecone to provide the LLM with comprehensive information for
generating Splunk TA configurations.

The PromptBuilder class provides:
- String-based prompt builders for each config type (inputs.conf, props.conf, etc.)
- Schema accessors for validating LLM responses
- Pinecone context retrieval and formatting

Example usage:
    ```python
    builder = PromptBuilder(pinecone_client)

    # Retrieve RAG context
    context = await builder.retrieve_context_from_pinecone(request, samples)

    # Build prompt with context
    prompt = await builder.build_ta_generation_prompt(
        request=request,
        log_samples=samples,
        sample_content_preview=preview,
        pinecone_context=context
    )

    # Get schema for response validation
    schema = builder.get_ta_generation_schema()
    ```
"""

from typing import Any, Dict, List

import structlog

from backend.integrations.pinecone_client import PineconeClient
from backend.models.request import Request
from backend.models.log_sample import LogSample

logger = structlog.get_logger(__name__)


# =============================================================================
# System Prompts and Templates
# =============================================================================


SYSTEM_PROMPT_TA_GENERATION = """You are an expert Splunk administrator and TA (Technology Add-on) developer.
Your task is to generate complete, production-ready Splunk TA configurations based on log samples and requirements.

You have deep knowledge of:
- Splunk props.conf, transforms.conf, inputs.conf configuration
- Regular expressions for field extraction
- Splunk Common Information Model (CIM) data models
- Best practices for timestamp parsing, line breaking, and field extraction

IMPORTANT CONSTRAINTS:
1. Generate valid Splunk configuration syntax only
2. Follow CIM naming conventions when mapping fields
3. Ensure all regular expressions are properly escaped
4. Include comprehensive comments in configurations
5. Handle edge cases like multi-line events and timestamp variations

Always respond with valid JSON conforming to the requested schema."""


TA_GENERATION_TEMPLATE = """Based on the following information, generate a complete Splunk Technology Add-on (TA).

## Request Details
- Request ID: {request_id}
- Source System: {source_system}
- Description: {description}
- CIM Compliance Required: {cim_required}

## Log Sample Preview
The following is a sample of the log data to be ingested:
```
{log_sample_preview}
```

## Relevant Splunk Knowledge
The following documentation and examples from our knowledge base may help:
{pinecone_context}

## Output Requirements
Generate a complete TA configuration with:
1. **inputs.conf** - Define the input source and sourcetype
2. **props.conf** - Define parsing rules (LINE_BREAKER, TIME_FORMAT, etc.)
3. **transforms.conf** - Define field extractions
4. **CIM Mappings** - Map extracted fields to CIM data models (if CIM compliance required)

Respond with a JSON object containing the complete TA configuration."""


INPUTS_CONF_TEMPLATE = """Generate a Splunk inputs.conf stanza for the following log source.

## Source Details
- Source System: {source_system}
- Log Type: {log_type}

## Relevant Documentation
{pinecone_docs}

## Requirements
1. Define appropriate sourcetype name
2. Configure index settings
3. Set appropriate input parameters

Respond with a JSON object containing the inputs.conf configuration."""


PROPS_CONF_TEMPLATE = """Generate a Splunk props.conf stanza for parsing the following log format.

## Sourcetype: {sourcetype}

## Log Sample
```
{sample_preview}
```

## Relevant Documentation
{pinecone_docs}

## Requirements
1. Determine LINE_BREAKER pattern
2. Set SHOULD_LINEMERGE appropriately
3. Configure TIME_PREFIX and TIME_FORMAT
4. Define TRUNCATE limit if needed

Respond with a JSON object containing the props.conf configuration."""


TRANSFORMS_CONF_TEMPLATE = """Generate Splunk transforms.conf stanzas for field extraction.

## Sourcetype: {sourcetype}

## Log Sample
```
{sample_preview}
```

## Relevant Documentation
{pinecone_docs}

## Requirements
1. Create REGEX patterns for field extraction
2. Define FORMAT specifications
3. Name fields following Splunk conventions
4. Consider performance impact of regex patterns

Respond with a JSON object containing the transforms.conf configuration."""


CIM_MAPPING_TEMPLATE = """Map the following extracted fields to Splunk CIM data models.

## Sourcetype: {sourcetype}

## Extracted Fields
{extracted_fields}

## CIM Documentation
{cim_docs}

## Requirements
1. Identify applicable CIM data models
2. Create field aliases for CIM compliance
3. Define calculated fields if needed
4. Ensure tag assignments for data model acceleration

Respond with a JSON object containing the CIM mappings."""


# =============================================================================
# JSON Response Schemas
# =============================================================================


TA_GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "ta_name": {"type": "string", "description": "Name of the TA (e.g., TA-custom-logs)"},
        "inputs_conf": {
            "type": "object",
            "properties": {
                "stanzas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stanza_name": {"type": "string"},
                            "settings": {"type": "object"}
                        }
                    }
                }
            }
        },
        "props_conf": {
            "type": "object",
            "properties": {
                "stanzas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stanza_name": {"type": "string"},
                            "settings": {"type": "object"}
                        }
                    }
                }
            }
        },
        "transforms_conf": {
            "type": "object",
            "properties": {
                "stanzas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stanza_name": {"type": "string"},
                            "settings": {"type": "object"}
                        }
                    }
                }
            }
        },
        "cim_mappings": {
            "type": "object",
            "properties": {
                "data_models": {"type": "array", "items": {"type": "string"}},
                "field_aliases": {"type": "object"},
                "calculated_fields": {"type": "array"},
                "tags": {"type": "object"}
            }
        }
    },
    "required": ["ta_name", "inputs_conf", "props_conf", "transforms_conf"]
}


INPUTS_CONF_SCHEMA = {
    "type": "object",
    "properties": {
        "stanzas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stanza_name": {"type": "string"},
                    "index": {"type": "string"},
                    "sourcetype": {"type": "string"},
                    "disabled": {"type": "boolean"},
                    "additional_settings": {"type": "object"}
                },
                "required": ["stanza_name", "sourcetype"]
            }
        }
    },
    "required": ["stanzas"]
}


PROPS_CONF_SCHEMA = {
    "type": "object",
    "properties": {
        "stanzas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stanza_name": {"type": "string"},
                    "LINE_BREAKER": {"type": "string"},
                    "SHOULD_LINEMERGE": {"type": "boolean"},
                    "TIME_PREFIX": {"type": "string"},
                    "TIME_FORMAT": {"type": "string"},
                    "MAX_TIMESTAMP_LOOKAHEAD": {"type": "integer"},
                    "TRUNCATE": {"type": "integer"},
                    "additional_settings": {"type": "object"}
                },
                "required": ["stanza_name"]
            }
        }
    },
    "required": ["stanzas"]
}


TRANSFORMS_CONF_SCHEMA = {
    "type": "object",
    "properties": {
        "stanzas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stanza_name": {"type": "string"},
                    "REGEX": {"type": "string"},
                    "FORMAT": {"type": "string"},
                    "WRITE_META": {"type": "boolean"},
                    "DEST_KEY": {"type": "string"}
                },
                "required": ["stanza_name", "REGEX"]
            }
        }
    },
    "required": ["stanzas"]
}


CIM_MAPPING_SCHEMA = {
    "type": "object",
    "properties": {
        "applicable_data_models": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of CIM data models this sourcetype maps to"
        },
        "field_aliases": {
            "type": "object",
            "description": "Map of original field names to CIM field names"
        },
        "calculated_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_name": {"type": "string"},
                    "expression": {"type": "string"}
                }
            }
        },
        "eventtypes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "search": {"type": "string"}
                }
            }
        },
        "tags": {
            "type": "object",
            "description": "Map of eventtype names to list of tags"
        }
    },
    "required": ["applicable_data_models", "field_aliases"]
}


# =============================================================================
# PromptBuilder Service
# =============================================================================


class PromptBuilder:
    """
    Service for constructing context-rich prompts for TA generation.

    Uses request metadata, log samples, and RAG context from Pinecone
    to build comprehensive prompts for the LLM.

    Example:
        ```python
        builder = PromptBuilder(pinecone_client)
        prompt = await builder.build_ta_generation_prompt(
            request=request,
            log_samples=samples,
            sample_content_preview=preview,
            pinecone_context=context
        )
        ```
    """

    def __init__(self, pinecone_client: PineconeClient):
        """
        Initialize PromptBuilder with Pinecone client.

        Args:
            pinecone_client: Client for retrieving RAG context
        """
        self.pinecone_client = pinecone_client
        self.logger = logger.bind(component="prompt_builder")
        self.logger.info("prompt_builder_initialized")

    async def build_ta_generation_prompt(
        self,
        request: Request,
        log_samples: List[LogSample],
        sample_content_preview: str,
        pinecone_context: Dict[str, List[Dict]],
    ) -> str:
        """
        Construct comprehensive prompt for full TA generation.

        Args:
            request: Request model with metadata
            log_samples: List of associated log samples
            sample_content_preview: First 50 lines of log content
            pinecone_context: Dict with keys "docs", "tas", "samples"

        Returns:
            Formatted prompt string ready for LLM
        """
        self.logger.info(
            "building_ta_generation_prompt",
            request_id=str(request.id),
            sample_count=len(log_samples),
            preview_length=len(sample_content_preview),
        )

        # Format Pinecone context
        formatted_context = self.format_pinecone_results(pinecone_context)

        # Truncate sample preview if too long (first 50 lines)
        lines = sample_content_preview.split("\n")
        truncated_preview = "\n".join(lines[:50])
        if len(lines) > 50:
            truncated_preview += f"\n... ({len(lines) - 50} more lines truncated)"

        # Build prompt from template
        prompt = TA_GENERATION_TEMPLATE.format(
            request_id=str(request.id),
            source_system=request.source_system or "Unknown",
            description=request.description or "No description provided",
            cim_required=request.cim_required if hasattr(request, "cim_required") else True,
            log_sample_preview=truncated_preview,
            pinecone_context=formatted_context,
        )

        self.logger.info(
            "ta_generation_prompt_built",
            request_id=str(request.id),
            prompt_length=len(prompt),
        )

        return prompt

    async def build_inputs_conf_prompt(
        self,
        request: Request,
        log_samples: List[LogSample],
        pinecone_docs: List[Dict],
    ) -> str:
        """
        Build focused prompt for inputs.conf generation.

        Args:
            request: Request model with metadata
            log_samples: List of associated log samples
            pinecone_docs: Relevant Splunk documentation

        Returns:
            Formatted prompt for inputs.conf generation
        """
        self.logger.info(
            "building_inputs_conf_prompt",
            request_id=str(request.id),
        )

        formatted_docs = self._format_doc_list(pinecone_docs)

        prompt = INPUTS_CONF_TEMPLATE.format(
            source_system=request.source_system or "Unknown",
            log_type=request.description or "Generic logs",
            pinecone_docs=formatted_docs,
        )

        return prompt

    async def build_props_conf_prompt(
        self,
        request: Request,
        sample_preview: str,
        pinecone_docs: List[Dict],
    ) -> str:
        """
        Build prompt for props.conf generation.

        Args:
            request: Request model with metadata
            sample_preview: Preview of log content
            pinecone_docs: Relevant Splunk documentation

        Returns:
            Formatted prompt for props.conf generation
        """
        self.logger.info(
            "building_props_conf_prompt",
            request_id=str(request.id),
        )

        formatted_docs = self._format_doc_list(pinecone_docs)
        sourcetype = self._derive_sourcetype(request)

        prompt = PROPS_CONF_TEMPLATE.format(
            sourcetype=sourcetype,
            sample_preview=sample_preview[:5000],  # Limit preview size
            pinecone_docs=formatted_docs,
        )

        return prompt

    async def build_transforms_conf_prompt(
        self,
        request: Request,
        sample_preview: str,
        pinecone_docs: List[Dict],
    ) -> str:
        """
        Build prompt for transforms.conf generation.

        Args:
            request: Request model with metadata
            sample_preview: Preview of log content
            pinecone_docs: Relevant Splunk documentation

        Returns:
            Formatted prompt for transforms.conf generation
        """
        self.logger.info(
            "building_transforms_conf_prompt",
            request_id=str(request.id),
        )

        formatted_docs = self._format_doc_list(pinecone_docs)
        sourcetype = self._derive_sourcetype(request)

        prompt = TRANSFORMS_CONF_TEMPLATE.format(
            sourcetype=sourcetype,
            sample_preview=sample_preview[:5000],  # Limit preview size
            pinecone_docs=formatted_docs,
        )

        return prompt

    async def build_cim_mapping_prompt(
        self,
        request: Request,
        extracted_fields: List[str],
        pinecone_docs: List[Dict],
    ) -> str:
        """
        Build prompt for CIM field mapping.

        Args:
            request: Request model with metadata
            extracted_fields: List of fields extracted by transforms
            pinecone_docs: CIM documentation from Pinecone

        Returns:
            Formatted prompt for CIM mapping generation
        """
        self.logger.info(
            "building_cim_mapping_prompt",
            request_id=str(request.id),
            field_count=len(extracted_fields),
        )

        formatted_docs = self._format_doc_list(pinecone_docs)
        sourcetype = self._derive_sourcetype(request)
        formatted_fields = "\n".join(f"- {field}" for field in extracted_fields)

        prompt = CIM_MAPPING_TEMPLATE.format(
            sourcetype=sourcetype,
            extracted_fields=formatted_fields,
            cim_docs=formatted_docs,
        )

        return prompt

    async def retrieve_context_from_pinecone(
        self,
        request: Request,
        log_samples: List[LogSample],
        top_k_per_source: int = 5,
    ) -> Dict[str, List[Dict]]:
        """
        Query Pinecone for relevant context.

        Args:
            request: Request model with metadata
            log_samples: List of log samples for context
            top_k_per_source: Number of results per source type

        Returns:
            Dict with keys "docs", "tas", "samples" containing retrieved context
        """
        self.logger.info(
            "retrieving_pinecone_context",
            request_id=str(request.id),
            top_k=top_k_per_source,
        )

        # Build query text from request metadata
        query_parts = []
        if request.source_system:
            query_parts.append(f"source system: {request.source_system}")
        if request.description:
            query_parts.append(request.description)

        query_text = " ".join(query_parts) if query_parts else "Splunk TA configuration"

        # Query Pinecone for all source types
        try:
            results = await self.pinecone_client.query_all_sources(
                query_text=query_text,
                top_k_per_source=top_k_per_source,
            )

            self.logger.info(
                "pinecone_context_retrieved",
                request_id=str(request.id),
                docs_count=len(results.get("docs", [])),
                tas_count=len(results.get("tas", [])),
                samples_count=len(results.get("samples", [])),
            )

            return results

        except Exception as e:
            self.logger.error(
                "pinecone_context_retrieval_failed",
                request_id=str(request.id),
                error=str(e),
            )
            # Return empty context on failure
            return {"docs": [], "tas": [], "samples": []}

    def format_pinecone_results(self, results: Dict[str, List[Dict]]) -> str:
        """
        Format Pinecone query results into readable text for prompt inclusion.

        Args:
            results: Dict with keys "docs", "tas", "samples"

        Returns:
            Formatted string with all context
        """
        sections = []

        # Format documentation results
        docs = results.get("docs", [])
        if docs:
            sections.append("### Relevant Splunk Documentation")
            for i, doc in enumerate(docs, 1):
                title = doc.get("title", "Untitled")
                content = doc.get("content", "")[:1000]  # Truncate long content
                score = doc.get("score", 0)
                sections.append(f"\n**{i}. {title}** (relevance: {score:.2f})")
                sections.append(content)

        # Format TA examples
        tas = results.get("tas", [])
        if tas:
            sections.append("\n### Similar TA Examples")
            for i, ta in enumerate(tas, 1):
                name = ta.get("name", "Unknown TA")
                content = ta.get("content", "")[:1500]  # Truncate
                score = ta.get("score", 0)
                sections.append(f"\n**{i}. {name}** (relevance: {score:.2f})")
                sections.append(f"```\n{content}\n```")

        # Format sample log patterns
        samples = results.get("samples", [])
        if samples:
            sections.append("\n### Similar Log Patterns")
            for i, sample in enumerate(samples, 1):
                source = sample.get("source", "Unknown")
                content = sample.get("content", "")[:500]  # Truncate
                score = sample.get("score", 0)
                sections.append(f"\n**{i}. {source}** (relevance: {score:.2f})")
                sections.append(f"```\n{content}\n```")

        if not sections:
            return "No relevant context found in knowledge base."

        return "\n".join(sections)

    def _format_doc_list(self, docs: List[Dict]) -> str:
        """Format a list of documents for prompt inclusion."""
        if not docs:
            return "No relevant documentation available."

        formatted = []
        for i, doc in enumerate(docs, 1):
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")[:1000]
            formatted.append(f"**{i}. {title}**\n{content}")

        return "\n\n".join(formatted)

    def _derive_sourcetype(self, request: Request) -> str:
        """Derive sourcetype name from request metadata."""
        if request.source_system:
            # Convert to valid sourcetype format
            sourcetype = request.source_system.lower()
            sourcetype = sourcetype.replace(" ", "_")
            sourcetype = "".join(c for c in sourcetype if c.isalnum() or c == "_")
            return sourcetype
        return "custom_logs"

    def get_system_prompt(self) -> str:
        """Get the system prompt for TA generation."""
        return SYSTEM_PROMPT_TA_GENERATION

    def get_ta_generation_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for TA generation response."""
        return TA_GENERATION_SCHEMA

    def get_inputs_conf_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for inputs.conf response."""
        return INPUTS_CONF_SCHEMA

    def get_props_conf_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for props.conf response."""
        return PROPS_CONF_SCHEMA

    def get_transforms_conf_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for transforms.conf response."""
        return TRANSFORMS_CONF_SCHEMA

    def get_cim_mapping_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for CIM mapping response."""
        return CIM_MAPPING_SCHEMA
