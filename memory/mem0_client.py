"""Mem0 integration wrapper for leaknote."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from mem0 import Memory
from qdrant_client import QdrantClient
from memory.config import MemoryConfig

logger = logging.getLogger(__name__)


class LeaknoteMemory:
    """
    Mem0 wrapper for leaknote.

    Manages semantic memory storage and retrieval for the second brain.
    """

    def __init__(self):
        """Initialize Mem0 with Qdrant backend."""
        self.config = MemoryConfig
        self._memory = None
        self._qdrant_client = None

    @property
    def memory(self) -> Memory:
        """Lazy initialization of Mem0 client."""
        if self._memory is None:
            # Initialize embedder with explicit OpenAI API key for embeddings
            # Uses text-embedding-3-small by default
            embedder_config = {}
            if self.config.OPENAI_API_KEY:
                embedder_config["api_key"] = self.config.OPENAI_API_KEY
                embedder_config["model"] = "text-embedding-3-small"

            # Configure Qdrant vector store
            # Parse URL to extract host and port for local Qdrant
            from urllib.parse import urlparse
            parsed = urlparse(self.config.QDRANT_URL)

            qdrant_config = {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 6333,
                "collection_name": self.config.MEM0_COLLECTION,
            }

            # Mem0 expects a plain dict for config
            config = {
                "vector_store": {
                    "provider": "qdrant",
                    "config": qdrant_config,
                },
                "embedder": {
                    "provider": "openai",
                    "config": embedder_config,
                },
            }

            self._memory = Memory.from_config(config)
            logger.info(f"Mem0 initialized with Qdrant at {self.config.QDRANT_URL}")
        return self._memory

    async def add_note_memory(
        self,
        note_id: str,
        category: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a note to semantic memory.

        Args:
            note_id: The database record ID
            category: The category (people, projects, ideas, etc.)
            content: The note content to extract memories from
            metadata: Additional metadata (tags, title, etc.)

        Returns:
            The memory ID
        """
        try:
            # Build enhanced context for memory extraction
            context = f"[{category.upper()}] {content}"

            # Prepare metadata
            memory_metadata = {
                "note_id": note_id,
                "category": category,
                "created_at": datetime.now().isoformat(),
                **(metadata or {}),
            }

            # Add to Mem0
            result = self.memory.add(
                context,
                user_id=self.config.MEM0_USER_ID,
                metadata=memory_metadata,
            )

            logger.info(f"Added memory for note {note_id} in {category}")
            return result

        except Exception as e:
            logger.error(f"Failed to add memory for note {note_id}: {e}")
            return ""

    async def search_relevant_context(
        self,
        query: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant memories given a query.

        Args:
            query: The search query
            limit: Maximum number of results (defaults to config)

        Returns:
            List of relevant memories with metadata
        """
        try:
            limit = limit or self.config.MEMORY_RETRIEVAL_LIMIT

            result = self.memory.search(
                query=query,
                user_id=self.config.MEM0_USER_ID,
                limit=limit,
            )

            # mem0 returns {"results": [...]} format
            if isinstance(result, dict):
                results = result.get("results", [])
            elif isinstance(result, list):
                results = result
            else:
                logger.error(f"Unexpected search result type: {type(result)}")
                return []

            logger.info(f"Found {len(results)} raw memories for query '{query}'")

            # Format results
            formatted = []
            for r in results:
                if isinstance(r, dict):
                    formatted.append({
                        "memory": r.get("memory", ""),
                        "metadata": r.get("metadata", {}),
                        "score": r.get("score", 0.0),
                    })
                else:
                    logger.warning(f"Unexpected result item type: {type(r)}")

            logger.info(f"Returning {len(formatted)} formatted memories")
            return formatted

        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []

    async def get_related_notes(
        self,
        note_content: str,
        category: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find related notes based on semantic similarity.

        Args:
            note_content: The content to find relations for
            category: The category of the note
            limit: Maximum number of related notes

        Returns:
            List of related note references with relevance scores
        """
        memories = await self.search_relevant_context(note_content, limit=limit)

        # Extract unique note IDs (exclude current note if needed)
        related = []
        seen_ids = set()

        for mem in memories:
            metadata = mem.get("metadata", {})
            note_id = metadata.get("note_id")

            if note_id and note_id not in seen_ids:
                seen_ids.add(note_id)
                related.append({
                    "note_id": note_id,
                    "category": metadata.get("category"),
                    "memory": mem["memory"],
                    "score": mem["score"],
                })

        return related[:limit]

    async def get_all_memories(
        self,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all memories, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of all memories
        """
        try:
            # mem0 returns {"results": [...]}
            result = self.memory.get_all(user_id=self.config.MEM0_USER_ID)

            if isinstance(result, dict):
                results = result.get("results", [])
            elif isinstance(result, list):
                results = result
            else:
                logger.error(f"Unexpected get_all result type: {type(result)}")
                return []

            if category:
                results = [
                    r for r in results
                    if r.get("metadata", {}).get("category") == category
                ]

            return results

        except Exception as e:
            logger.error(f"Failed to get all memories: {e}")
            return []

    async def delete_note_memories(self, note_id: str) -> bool:
        """
        Delete all memories associated with a note.

        Args:
            note_id: The database record ID

        Returns:
            True if successful
        """
        try:
            # Get all memories for this note
            result = self.memory.get_all(user_id=self.config.MEM0_USER_ID)

            # mem0 returns {"results": [...]}
            if isinstance(result, dict):
                all_memories = result.get("results", [])
            elif isinstance(result, list):
                all_memories = result
            else:
                logger.error(f"Unexpected get_all result type: {type(result)}")
                return False

            # Filter and delete
            for mem in all_memories:
                if mem.get("metadata", {}).get("note_id") == note_id:
                    self.memory.delete(memory_id=mem["id"])

            logger.info(f"Deleted memories for note {note_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete memories for note {note_id}: {e}")
            return False

    async def update_note_memory(
        self,
        note_id: str,
        new_content: str,
        category: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update memories when a note is edited.

        Args:
            note_id: The database record ID
            new_content: The updated content
            category: The category
            metadata: Additional metadata

        Returns:
            True if successful
        """
        try:
            # Delete old memories
            await self.delete_note_memories(note_id)

            # Add new memories
            await self.add_note_memory(note_id, category, new_content, metadata)

            logger.info(f"Updated memories for note {note_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update memories for note {note_id}: {e}")
            return False


# Singleton instance
_memory_client: Optional[LeaknoteMemory] = None


def get_memory_client() -> LeaknoteMemory:
    """Get the singleton memory client."""
    global _memory_client
    if _memory_client is None:
        _memory_client = LeaknoteMemory()
    return _memory_client
