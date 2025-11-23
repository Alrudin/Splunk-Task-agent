"""
Pinecone vector database client for semantic search and RAG.

Provides async operations for document indexing, embedding generation,
and semantic search across Splunk docs, TA examples, and sample logs.
"""
import asyncio
from typing import Any, Dict, List, Optional

import structlog
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

from backend.core.config import settings

logger = structlog.get_logger(__name__)


class PineconeClientError(Exception):
    """Base exception for Pinecone client errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize Pinecone client error.

        Args:
            message: Error message
            details: Optional additional error details
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class IndexNotFoundError(PineconeClientError):
    """Exception raised when a Pinecone index is not found."""

    pass


class EmbeddingError(PineconeClientError):
    """Exception raised when embedding generation fails."""

    pass


class QueryError(PineconeClientError):
    """Exception raised when a query operation fails."""

    pass


class UpsertError(PineconeClientError):
    """Exception raised when an upsert operation fails."""

    pass


class EmbeddingGenerator:
    """
    Embedding generator using sentence-transformers.

    Provides methods for text encoding, chunking, and batch processing
    optimized for technical documentation and log content.
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize embedding generator with specified model.

        Args:
            model_name: Sentence transformer model name (defaults to settings)
        """
        self.model_name = model_name or settings.embedding_model_name
        self.batch_size = settings.embedding_batch_size
        self.normalize = settings.embedding_normalize

        logger.info(
            "embedding_generator_initializing",
            model_name=self.model_name,
            batch_size=self.batch_size,
            normalize=self.normalize,
        )

        # Load model (this is CPU/GPU intensive, so we do it once)
        self.model = SentenceTransformer(self.model_name)

        logger.info(
            "embedding_generator_initialized",
            model_name=self.model_name,
            dimension=self.dimension,
        )

    @property
    def dimension(self) -> int:
        """
        Get embedding dimension for this model.

        Returns:
            Embedding vector dimension
        """
        # Get dimension from model's pooling layer
        return self.model.get_sentence_embedding_dimension()

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to encode

        Returns:
            List of embedding vectors (each vector is a list of floats)

        Raises:
            EmbeddingError: If encoding fails
        """
        if not texts:
            return []

        log = logger.bind(num_texts=len(texts), batch_size=self.batch_size)
        log.info("generate_embeddings_started")

        try:
            # Encode texts in batches
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=self.normalize,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            # Convert numpy arrays to lists
            embeddings_list = [emb.tolist() for emb in embeddings]

            log.info("generate_embeddings_completed", num_embeddings=len(embeddings_list))
            return embeddings_list

        except Exception as e:
            log.error("generate_embeddings_failed", error=str(e))
            raise EmbeddingError(
                f"Failed to generate embeddings for {len(texts)} texts",
                {"num_texts": len(texts), "error": str(e)},
            ) from e

    def generate_single_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to encode

        Returns:
            Embedding vector as list of floats

        Raises:
            EmbeddingError: If encoding fails
        """
        embeddings = self.generate_embeddings([text])
        return embeddings[0] if embeddings else []

    def chunk_text(
        self,
        text: str,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ) -> List[str]:
        """
        Split text into overlapping chunks by word count.

        Args:
            text: Text to chunk
            chunk_size: Words per chunk (defaults to settings)
            overlap: Overlap words between chunks (defaults to settings)

        Returns:
            List of text chunks
        """
        chunk_size = chunk_size or settings.chunk_size_words
        overlap = overlap or settings.chunk_overlap_words

        # Split into words
        words = text.split()

        if len(words) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        step = max(1, chunk_size - overlap)

        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))

            # Move start position with step
            start += step

        # Apply max chunks limit
        max_chunks = settings.max_chunks_per_document
        if len(chunks) > max_chunks:
            logger.warning(
                "chunk_limit_exceeded",
                total_chunks=len(chunks),
                max_chunks=max_chunks,
                text_length=len(text),
            )
            chunks = chunks[:max_chunks]

        return chunks


class PineconeClient:
    """
    Client for Pinecone vector database operations.

    Provides methods for index management, document upserting,
    semantic search, and specialized queries for different content types.
    """

    def __init__(self):
        """Initialize Pinecone client with settings from config."""
        self.api_key = settings.pinecone_api_key
        self.environment = settings.pinecone_environment
        self.cloud = settings.pinecone_cloud
        self.region = settings.pinecone_region

        # Index names
        self.index_docs = settings.pinecone_index_docs
        self.index_tas = settings.pinecone_index_tas
        self.index_samples = settings.pinecone_index_samples

        # Vector settings
        self.dimension = settings.pinecone_dimension
        self.metric = settings.pinecone_metric

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=self.api_key)

        # Initialize embedding generator
        self.embedding_generator = EmbeddingGenerator()

        # Verify dimension matches model
        if self.embedding_generator.dimension != self.dimension:
            logger.warning(
                "dimension_mismatch",
                config_dimension=self.dimension,
                model_dimension=self.embedding_generator.dimension,
            )
            # Use model's actual dimension
            self.dimension = self.embedding_generator.dimension

        logger.info(
            "pinecone_client_initialized",
            environment=self.environment,
            cloud=self.cloud,
            region=self.region,
            indexes={
                "docs": self.index_docs,
                "tas": self.index_tas,
                "samples": self.index_samples,
            },
            dimension=self.dimension,
            metric=self.metric,
            embedding_model=settings.embedding_model_name,
        )

    async def ensure_index_exists(
        self,
        index_name: str,
        dimension: Optional[int] = None,
        metric: Optional[str] = None,
    ) -> None:
        """
        Create index if it doesn't exist using serverless spec.

        Args:
            index_name: Name of the index to create
            dimension: Embedding dimension (defaults to client dimension)
            metric: Distance metric (defaults to client metric)

        Raises:
            PineconeClientError: If index creation fails
        """
        dimension = dimension or self.dimension
        metric = metric or self.metric

        log = logger.bind(index_name=index_name, dimension=dimension, metric=metric)
        log.info("ensure_index_exists_started")

        try:
            # Run synchronous operation in thread pool
            existing_indexes = await asyncio.to_thread(
                lambda: [idx.name for idx in self.pc.list_indexes()]
            )

            if index_name in existing_indexes:
                log.info("index_already_exists")
                return

            # Create serverless index
            await asyncio.to_thread(
                self.pc.create_index,
                name=index_name,
                dimension=dimension,
                metric=metric,
                spec=ServerlessSpec(cloud=self.cloud, region=self.region),
            )

            log.info("index_created")

        except Exception as e:
            log.error("ensure_index_exists_failed", error=str(e))
            raise PineconeClientError(
                f"Failed to ensure index '{index_name}' exists",
                {"index_name": index_name, "error": str(e)},
            ) from e

    async def list_indexes(self) -> List[str]:
        """
        List all available Pinecone indexes.

        Returns:
            List of index names

        Raises:
            PineconeClientError: If listing fails
        """
        logger.info("list_indexes_started")

        try:
            indexes = await asyncio.to_thread(
                lambda: [idx.name for idx in self.pc.list_indexes()]
            )

            logger.info("list_indexes_completed", count=len(indexes), indexes=indexes)
            return indexes

        except Exception as e:
            logger.error("list_indexes_failed", error=str(e))
            raise PineconeClientError(
                "Failed to list indexes",
                {"error": str(e)},
            ) from e

    async def delete_index(self, index_name: str) -> None:
        """
        Delete a Pinecone index.

        Args:
            index_name: Name of the index to delete

        Raises:
            PineconeClientError: If deletion fails
        """
        log = logger.bind(index_name=index_name)
        log.info("delete_index_started")

        try:
            await asyncio.to_thread(self.pc.delete_index, index_name)
            log.info("delete_index_completed")

        except Exception as e:
            log.error("delete_index_failed", error=str(e))
            raise PineconeClientError(
                f"Failed to delete index '{index_name}'",
                {"index_name": index_name, "error": str(e)},
            ) from e

    async def get_index_stats(self, index_name: str) -> Dict[str, Any]:
        """
        Get statistics for a Pinecone index.

        Args:
            index_name: Name of the index

        Returns:
            Dict with index statistics

        Raises:
            IndexNotFoundError: If index doesn't exist
            PineconeClientError: If stats retrieval fails
        """
        log = logger.bind(index_name=index_name)
        log.info("get_index_stats_started")

        try:
            index = self.pc.Index(index_name)
            stats = await asyncio.to_thread(index.describe_index_stats)

            stats_dict = {
                "dimension": stats.get("dimension"),
                "index_fullness": stats.get("index_fullness"),
                "total_vector_count": stats.get("total_vector_count"),
                "namespaces": stats.get("namespaces", {}),
            }

            log.info("get_index_stats_completed", stats=stats_dict)
            return stats_dict

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                log.warning("index_not_found")
                raise IndexNotFoundError(
                    f"Index '{index_name}' not found",
                    {"index_name": index_name},
                ) from e

            log.error("get_index_stats_failed", error=str(e))
            raise PineconeClientError(
                f"Failed to get stats for index '{index_name}'",
                {"index_name": index_name, "error": str(e)},
            ) from e

    def _prepare_upsert_batch(
        self,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> List[Dict[str, Any]]:
        """
        Prepare documents and embeddings for Pinecone upsert.

        Args:
            documents: List of documents with id, text, metadata
            embeddings: List of embedding vectors

        Returns:
            List of vectors formatted for Pinecone upsert
        """
        vectors = []
        for doc, embedding in zip(documents, embeddings):
            vector = {
                "id": doc["id"],
                "values": embedding,
                "metadata": {
                    **doc.get("metadata", {}),
                    "text": doc["text"][:1000],  # Limit text in metadata to 1000 chars
                },
            }
            vectors.append(vector)

        return vectors

    def _chunk_document(
        self,
        text: str,
        doc_id: str,
        metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Chunk a document and prepare multiple chunk documents.

        Args:
            text: Document text to chunk
            doc_id: Base document ID
            metadata: Metadata to attach to each chunk

        Returns:
            List of document dicts with chunk IDs and text
        """
        chunks = self.embedding_generator.chunk_text(text)

        chunked_docs = []
        for i, chunk in enumerate(chunks):
            chunked_docs.append({
                "id": f"{doc_id}_chunk_{i}",
                "text": chunk,
                "metadata": {
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "parent_doc_id": doc_id,
                },
            })

        return chunked_docs

    async def upsert_documents(
        self,
        index_name: str,
        documents: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Upsert documents with automatic chunking and embedding.

        Each document dict should contain:
        - id: Unique document identifier
        - text: Document text content
        - metadata: Optional metadata dict

        Args:
            index_name: Target index name
            documents: List of document dicts
            batch_size: Number of vectors per upsert batch

        Returns:
            Dict with document_count (source documents) and vector_count (chunked vectors upserted)

        Raises:
            IndexNotFoundError: If index doesn't exist
            UpsertError: If upsert fails
        """
        log = logger.bind(
            index_name=index_name,
            num_documents=len(documents),
            batch_size=batch_size,
        )
        log.info("upsert_documents_started")

        try:
            # Check if index exists
            index = self.pc.Index(index_name)

            # Chunk all documents
            all_chunks = []
            for doc in documents:
                chunks = self._chunk_document(
                    text=doc["text"],
                    doc_id=doc["id"],
                    metadata=doc.get("metadata", {}),
                )
                all_chunks.extend(chunks)

            log.info("documents_chunked", total_chunks=len(all_chunks))

            # Generate embeddings for all chunks (CPU-bound operation)
            texts = [chunk["text"] for chunk in all_chunks]
            embeddings = await asyncio.to_thread(
                self.embedding_generator.generate_embeddings,
                texts,
            )

            log.info("embeddings_generated", num_embeddings=len(embeddings))

            # Prepare vectors for upsert
            vectors = self._prepare_upsert_batch(all_chunks, embeddings)

            # Upsert in batches
            upserted_count = 0
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                await asyncio.to_thread(index.upsert, vectors=batch)
                upserted_count += len(batch)

                log.info(
                    "batch_upserted",
                    batch_num=i // batch_size + 1,
                    batch_size=len(batch),
                    total_upserted=upserted_count,
                )

            result = {
                "document_count": len(documents),
                "vector_count": upserted_count,
            }

            log.info("upsert_documents_completed", result=result)
            return result

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                log.warning("index_not_found")
                raise IndexNotFoundError(
                    f"Index '{index_name}' not found",
                    {"index_name": index_name},
                ) from e

            log.error("upsert_documents_failed", error=str(e))
            raise UpsertError(
                f"Failed to upsert documents to index '{index_name}'",
                {"index_name": index_name, "num_documents": len(documents), "error": str(e)},
            ) from e

    async def upsert_vectors(
        self,
        index_name: str,
        vectors: List[Dict[str, Any]],
    ) -> None:
        """
        Directly upsert pre-embedded vectors.

        Each vector dict should contain:
        - id: Unique vector identifier
        - values: Embedding vector (list of floats)
        - metadata: Optional metadata dict

        Args:
            index_name: Target index name
            vectors: List of vector dicts

        Raises:
            IndexNotFoundError: If index doesn't exist
            UpsertError: If upsert fails
        """
        log = logger.bind(index_name=index_name, num_vectors=len(vectors))
        log.info("upsert_vectors_started")

        try:
            index = self.pc.Index(index_name)
            await asyncio.to_thread(index.upsert, vectors=vectors)

            log.info("upsert_vectors_completed")

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                log.warning("index_not_found")
                raise IndexNotFoundError(
                    f"Index '{index_name}' not found",
                    {"index_name": index_name},
                ) from e

            log.error("upsert_vectors_failed", error=str(e))
            raise UpsertError(
                f"Failed to upsert vectors to index '{index_name}'",
                {"index_name": index_name, "num_vectors": len(vectors), "error": str(e)},
            ) from e

    async def query_similar(
        self,
        index_name: str,
        query_text: str,
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for similar documents using query text.

        Args:
            index_name: Index to query
            query_text: Query text to find similar documents
            top_k: Number of results to return (defaults to settings)
            filter_dict: Optional metadata filter
            include_metadata: Include metadata in results

        Returns:
            List of matches with id, score, metadata, text

        Raises:
            IndexNotFoundError: If index doesn't exist
            QueryError: If query fails
        """
        top_k = top_k or settings.pinecone_top_k

        log = logger.bind(
            index_name=index_name,
            query_text=query_text[:100],  # Log truncated query
            top_k=top_k,
            has_filter=filter_dict is not None,
        )
        log.info("query_similar_started")

        try:
            # Generate query embedding (CPU-bound)
            query_vector = await asyncio.to_thread(
                self.embedding_generator.generate_single_embedding,
                query_text,
            )

            # Query with timeout
            index = self.pc.Index(index_name)
            timeout = settings.pinecone_query_timeout

            query_params = {
                "vector": query_vector,
                "top_k": top_k,
                "include_metadata": include_metadata,
            }
            if filter_dict:
                query_params["filter"] = filter_dict

            results = await asyncio.wait_for(
                asyncio.to_thread(index.query, **query_params),
                timeout=timeout,
            )

            # Format results
            matches = []
            for match in results.matches:
                match_dict = {
                    "id": match.id,
                    "score": match.score,
                }
                if include_metadata and match.metadata:
                    match_dict["metadata"] = match.metadata
                    match_dict["text"] = match.metadata.get("text", "")

                matches.append(match_dict)

            log.info("query_similar_completed", num_results=len(matches))
            return matches

        except asyncio.TimeoutError as e:
            log.error("query_similar_timeout", timeout=timeout)
            raise QueryError(
                f"Query to index '{index_name}' timed out after {timeout}s",
                {"index_name": index_name, "timeout": timeout},
            ) from e
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                log.warning("index_not_found")
                raise IndexNotFoundError(
                    f"Index '{index_name}' not found",
                    {"index_name": index_name},
                ) from e

            log.error("query_similar_failed", error=str(e))
            raise QueryError(
                f"Failed to query index '{index_name}'",
                {"index_name": index_name, "error": str(e)},
            ) from e

    async def query_by_vector(
        self,
        index_name: str,
        vector: List[float],
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query using a pre-computed embedding vector.

        Args:
            index_name: Index to query
            vector: Query embedding vector
            top_k: Number of results to return (defaults to settings)
            filter_dict: Optional metadata filter

        Returns:
            List of matches with id, score, metadata

        Raises:
            IndexNotFoundError: If index doesn't exist
            QueryError: If query fails
        """
        top_k = top_k or settings.pinecone_top_k

        log = logger.bind(
            index_name=index_name,
            vector_dim=len(vector),
            top_k=top_k,
        )
        log.info("query_by_vector_started")

        try:
            index = self.pc.Index(index_name)

            query_params = {
                "vector": vector,
                "top_k": top_k,
                "include_metadata": True,
            }
            if filter_dict:
                query_params["filter"] = filter_dict

            results = await asyncio.to_thread(index.query, **query_params)

            matches = []
            for match in results.matches:
                matches.append({
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata if match.metadata else {},
                })

            log.info("query_by_vector_completed", num_results=len(matches))
            return matches

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                log.warning("index_not_found")
                raise IndexNotFoundError(
                    f"Index '{index_name}' not found",
                    {"index_name": index_name},
                ) from e

            log.error("query_by_vector_failed", error=str(e))
            raise QueryError(
                f"Failed to query index '{index_name}' by vector",
                {"index_name": index_name, "error": str(e)},
            ) from e

    async def query_splunk_docs(
        self,
        query_text: str,
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query Splunk documentation index.

        Args:
            query_text: Query text
            top_k: Number of results
            filter_dict: Optional metadata filter

        Returns:
            List of matching Splunk documentation excerpts
        """
        logger.info("query_splunk_docs", query_text=query_text[:100], top_k=top_k)
        return await self.query_similar(
            index_name=self.index_docs,
            query_text=query_text,
            top_k=top_k,
            filter_dict=filter_dict,
        )

    async def query_ta_examples(
        self,
        query_text: str,
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query historical TA examples index.

        Args:
            query_text: Query text
            top_k: Number of results
            filter_dict: Optional metadata filter

        Returns:
            List of matching TA examples
        """
        logger.info("query_ta_examples", query_text=query_text[:100], top_k=top_k)
        return await self.query_similar(
            index_name=self.index_tas,
            query_text=query_text,
            top_k=top_k,
            filter_dict=filter_dict,
        )

    async def query_sample_logs(
        self,
        query_text: str,
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query sample logs index.

        Args:
            query_text: Query text
            top_k: Number of results
            filter_dict: Optional metadata filter

        Returns:
            List of matching sample log excerpts
        """
        logger.info("query_sample_logs", query_text=query_text[:100], top_k=top_k)
        return await self.query_similar(
            index_name=self.index_samples,
            query_text=query_text,
            top_k=top_k,
            filter_dict=filter_dict,
        )

    async def query_all_sources(
        self,
        query_text: str,
        top_k_per_source: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Query all three indexes in parallel and return combined results.

        Args:
            query_text: Query text
            top_k_per_source: Number of results per source type

        Returns:
            Dict with keys "docs", "tas", "samples" containing results from each index
        """
        logger.info(
            "query_all_sources",
            query_text=query_text[:100],
            top_k_per_source=top_k_per_source,
        )

        # Query all indexes in parallel
        docs_task = self.query_splunk_docs(query_text, top_k=top_k_per_source)
        tas_task = self.query_ta_examples(query_text, top_k=top_k_per_source)
        samples_task = self.query_sample_logs(query_text, top_k=top_k_per_source)

        docs_results, tas_results, samples_results = await asyncio.gather(
            docs_task,
            tas_task,
            samples_task,
            return_exceptions=True,
        )

        # Handle exceptions gracefully
        result = {
            "docs": docs_results if not isinstance(docs_results, Exception) else [],
            "tas": tas_results if not isinstance(tas_results, Exception) else [],
            "samples": samples_results if not isinstance(samples_results, Exception) else [],
        }

        # Log any errors
        if isinstance(docs_results, Exception):
            logger.error("query_all_sources_docs_failed", error=str(docs_results))
        if isinstance(tas_results, Exception):
            logger.error("query_all_sources_tas_failed", error=str(tas_results))
        if isinstance(samples_results, Exception):
            logger.error("query_all_sources_samples_failed", error=str(samples_results))

        total_results = len(result["docs"]) + len(result["tas"]) + len(result["samples"])
        logger.info("query_all_sources_completed", total_results=total_results)

        return result

    async def delete_vectors(self, index_name: str, ids: List[str]) -> None:
        """
        Delete vectors by ID from an index.

        Args:
            index_name: Target index name
            ids: List of vector IDs to delete

        Raises:
            IndexNotFoundError: If index doesn't exist
            PineconeClientError: If deletion fails
        """
        log = logger.bind(index_name=index_name, num_ids=len(ids))
        log.info("delete_vectors_started")

        try:
            index = self.pc.Index(index_name)
            await asyncio.to_thread(index.delete, ids=ids)

            log.info("delete_vectors_completed")

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                log.warning("index_not_found")
                raise IndexNotFoundError(
                    f"Index '{index_name}' not found",
                    {"index_name": index_name},
                ) from e

            log.error("delete_vectors_failed", error=str(e))
            raise PineconeClientError(
                f"Failed to delete vectors from index '{index_name}'",
                {"index_name": index_name, "num_ids": len(ids), "error": str(e)},
            ) from e

    async def delete_by_filter(
        self,
        index_name: str,
        filter_dict: Dict[str, Any],
    ) -> None:
        """
        Delete vectors matching metadata filter.

        Args:
            index_name: Target index name
            filter_dict: Metadata filter for deletion

        Raises:
            IndexNotFoundError: If index doesn't exist
            PineconeClientError: If deletion fails
        """
        log = logger.bind(index_name=index_name, filter=filter_dict)
        log.info("delete_by_filter_started")

        try:
            index = self.pc.Index(index_name)
            await asyncio.to_thread(index.delete, filter=filter_dict)

            log.info("delete_by_filter_completed")

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                log.warning("index_not_found")
                raise IndexNotFoundError(
                    f"Index '{index_name}' not found",
                    {"index_name": index_name},
                ) from e

            log.error("delete_by_filter_failed", error=str(e))
            raise PineconeClientError(
                f"Failed to delete by filter from index '{index_name}'",
                {"index_name": index_name, "filter": filter_dict, "error": str(e)},
            ) from e

    async def update_metadata(
        self,
        index_name: str,
        id: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        Update metadata for a vector.

        Args:
            index_name: Target index name
            id: Vector ID to update
            metadata: New metadata dict

        Raises:
            IndexNotFoundError: If index doesn't exist
            PineconeClientError: If update fails
        """
        log = logger.bind(index_name=index_name, vector_id=id)
        log.info("update_metadata_started")

        try:
            index = self.pc.Index(index_name)
            await asyncio.to_thread(
                index.update,
                id=id,
                set_metadata=metadata,
            )

            log.info("update_metadata_completed")

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                log.warning("index_not_found")
                raise IndexNotFoundError(
                    f"Index '{index_name}' not found",
                    {"index_name": index_name},
                ) from e

            log.error("update_metadata_failed", error=str(e))
            raise PineconeClientError(
                f"Failed to update metadata for vector '{id}' in index '{index_name}'",
                {"index_name": index_name, "vector_id": id, "error": str(e)},
            ) from e
