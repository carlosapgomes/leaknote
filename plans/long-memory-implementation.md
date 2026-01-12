# Long-Term Memory Implementation Plan for Leaknote

## Overview

This document outlines the implementation of a long-term memory layer for leaknote using **Mem0** (semantic memory) and **LangGraph** (orchestration engine), with **Qdrant** as the vector database.

### Architecture Principles

- **PostgreSQL** remains the source of truth for structured data
- **Mem0** acts as a semantic memory layer for extracting and retrieving knowledge
- **LangGraph** orchestrates the "thinking" process for note analysis
- **Qdrant** provides the vector storage backend for Mem0

```
                    ┌─────────────────────────────────────────┐
                    │         Telegram Bot Interface           │
                    └─────────────────┬───────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │        Message Router (Existing)         │
                    │    - Prefix detection                    │
                    │    - LLM classification                  │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────┴───────────────────────┐
                    │                                           │
                    ▼                                           ▼
        ┌───────────────────────┐               ┌───────────────────────┐
        │  PostgreSQL Storage   │               │   Memory Layer (NEW)  │
        │  (Source of Truth)    │               │   - Mem0 + Qdrant     │
        └───────────────────────┘               │   - LangGraph Brain   │
                                                └───────────────────────┘
                                                            │
                    ┌───────────────────────────────────────┴───────────────┐
                    │                                                       │
                    ▼                                                       ▼
        ┌───────────────────────┐                           ┌───────────────────────┐
        │  Smart Linking        │                           │  Weekly Reflection     │
        │  - Suggest [[links]]  │                           │  - Pattern detection  │
        │  - Context retrieval  │                           │  - Insight generation │
        └───────────────────────┘                           └───────────────────────┘
```

---

## Phase 1: Infrastructure Setup ✅ COMPLETED

### 1.1 Docker Compose - Add Qdrant

**File:** `docker-compose.yml`

Add Qdrant service before PostgreSQL:

```yaml
  qdrant:
    image: qdrant/qdrant:v1.12.0
    container_name: leaknote-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./data/qdrant:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - leaknote-net
```

Update leaknote service to depend on Qdrant:
```yaml
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
```

Add Qdrant URL to leaknote environment:
```yaml
      QDRANT_URL: http://qdrant:6333
```

---

### 1.2 Python Dependencies

**File:** `requirements.txt`

Add new dependencies:

```txt
python-telegram-bot==20.7
asyncpg==0.29.0
httpx~=0.25.2
python-dotenv==1.0.1
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
jinja2>=3.1.2
python-multipart>=0.0.6
markdown>=3.5.0

# Long-term memory dependencies
mem0ai>=0.1.0
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.2.0
qdrant-client>=1.12.0
```

---

### 1.3 Environment Configuration

**File:** `.env.example`

Add new configuration variables:

```bash
# =============================================================================
# Memory Layer - Mem0 + Qdrant
# =============================================================================

# Qdrant connection
QDRANT_URL=http://qdrant:6333
# For local development (outside Docker), use: http://localhost:6333

# Memory LLM (for LangGraph orchestration)
# This should be a high-quality model for reasoning and memory extraction
MEMORY_PROVIDER=openai
MEMORY_API_URL=https://api.openai.com/v1
MEMORY_API_KEY=your-memory-api-key
MEMORY_MODEL=gpt-4o

# Collection names in Qdrant
MEM0_COLLECTION=leaknote_memories

# Memory settings
MEMORY_RETRIEVAL_LIMIT=5  # Number of memories to retrieve for context
MEMORY_CONFIDENCE_THRESHOLD=0.7  # Minimum similarity for memory matches
```

---

## Phase 2: Memory Layer Implementation ✅ COMPLETED

### 2.1 Memory Configuration Module

**File:** `memory/config.py`

Create a configuration module for the memory layer:

```python
"""Memory layer configuration."""

import os
from dotenv import load_dotenv

load_dotenv()


class MemoryConfig:
    """Configuration for Mem0 and LangGraph."""

    # Qdrant
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    MEM0_COLLECTION = os.getenv("MEM0_COLLECTION", "leaknote_memories")

    # Memory LLM (for LangGraph orchestration)
    MEMORY_PROVIDER = os.getenv("MEMORY_PROVIDER", "openai")
    MEMORY_API_URL = os.getenv("MEMORY_API_URL")
    MEMORY_API_KEY = os.getenv("MEMORY_API_KEY")
    MEMORY_MODEL = os.getenv("MEMORY_MODEL", "gpt-4o")

    # Settings
    MEMORY_RETRIEVAL_LIMIT = int(os.getenv("MEMORY_RETRIEVAL_LIMIT", "5"))
    MEMORY_CONFIDENCE_THRESHOLD = float(os.getenv("MEMORY_CONFIDENCE_THRESHOLD", "0.7"))

    # User ID for Mem0 (single-user system)
    MEM0_USER_ID = "leaknote_user"

    # Cached client
    _llm_client = None

    @classmethod
    def get_llm_client(cls):
        """Get or create the LLM client for memory operations."""
        if cls._llm_client is None:
            from llm.factory import create_client
            cls._llm_client = create_client(
                provider=cls.MEMORY_PROVIDER,
                api_url=cls.MEMORY_API_URL,
                api_key=cls.MEMORY_API_KEY,
                model=cls.MEMORY_MODEL,
            )
        return cls._llm_client

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration."""
        required = [
            ("QDRANT_URL", cls.QDRANT_URL),
            ("MEMORY_API_URL", cls.MEMORY_API_URL),
            ("MEMORY_API_KEY", cls.MEMORY_API_KEY),
        ]
        return [name for name, value in required if not value]
```

---

### 2.2 Mem0 Client Wrapper

**File:** `memory/mem0_client.py`

Create a wrapper around Mem0 for leaknote-specific operations:

```python
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
            from mem0.configs.embedders import OpenAIEmbedderConfig

            self._memory = Memory(
                vector_store="qdrant",
                embedder=OpenAIEmbedderConfig(),
                collection_name=self.config.MEM0_COLLECTION,
                qdrant_url=self.config.QDRANT_URL,
            )
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

            results = self.memory.search(
                query=query,
                user_id=self.config.MEM0_USER_ID,
                limit=limit,
            )

            # Format results
            formatted = []
            for r in results:
                formatted.append({
                    "memory": r.get("memory", ""),
                    "metadata": r.get("metadata", {}),
                    "score": r.get("score", 0.0),
                })

            logger.info(f"Found {len(formatted)} relevant memories for query")
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
            # Mem0 doesn't have a direct "get all" - we need to use get_all
            results = self.memory.get_all(user_id=self.config.MEM0_USER_ID)

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
            all_memories = self.memory.get_all(user_id=self.config.MEM0_USER_ID)

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
```

---

### 2.3 LangGraph Orchestration Brain

**File:** `memory/graph.py`

Create the LangGraph-based "brain" for intelligent note processing:

```python
"""LangGraph-based orchestration for intelligent note processing."""

import logging
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

from langgraph.graph import StateGraph, END
from memory.config import MemoryConfig
from memory.mem0_client import get_memory_client

logger = logging.getLogger(__name__)


class BrainState(TypedDict):
    """State for the memory-enhanced note processing flow."""
    input_note: str
    category: str
    note_id: Optional[str]
    extracted_fields: Dict[str, Any]
    relevant_memories: List[Dict[str, Any]]
    related_notes: List[Dict[str, Any]]
    suggested_links: List[str]
    enhanced_note: Optional[str]
    metadata: Dict[str, Any]


class MemoryBrain:
    """
    LangGraph-based orchestration for memory-aware note processing.

    This brain:
    1. Retrieves relevant context from Mem0
    2. Finds semantically related notes
    3. Suggests internal [[links]]
    4. Extracts and stores new memories
    """

    def __init__(self):
        self.config = MemoryConfig
        self.memory_client = get_memory_client()
        self._graph = None

    @property
    def graph(self):
        """Lazy initialization of the LangGraph."""
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph for memory-aware processing."""

        # Define the graph
        workflow = StateGraph(BrainState)

        # Add nodes
        workflow.add_node("retrieve_memories", self._retrieve_memories)
        workflow.add_node("find_relations", self._find_relations)
        workflow.add_node("generate_links", self._generate_links)
        workflow.add_node("store_memory", self._store_memory)

        # Define edges
        workflow.set_entry_point("retrieve_memories")
        workflow.add_edge("retrieve_memories", "find_relations")
        workflow.add_edge("find_relations", "generate_links")
        workflow.add_edge("generate_links", "store_memory")
        workflow.add_edge("store_memory", END)

        return workflow.compile()

    async def _retrieve_memories(self, state: BrainState) -> BrainState:
        """Retrieve relevant memories from Mem0 based on the input."""
        logger.info("Retrieving relevant memories...")

        memories = await self.memory_client.search_relevant_context(
            query=state["input_note"],
            limit=self.config.MEMORY_RETRIEVAL_LIMIT,
        )

        state["relevant_memories"] = memories
        logger.info(f"Retrieved {len(memories)} relevant memories")
        return state

    async def _find_relations(self, state: BrainState) -> BrainState:
        """Find semantically related notes."""
        logger.info("Finding related notes...")

        related = await self.memory_client.get_related_notes(
            note_content=state["input_note"],
            category=state["category"],
            limit=5,
        )

        state["related_notes"] = related
        logger.info(f"Found {len(related)} related notes")
        return state

    async def _generate_links(self, state: BrainState) -> BrainState:
        """Generate suggested [[links]] based on related notes."""
        logger.info("Generating link suggestions...")

        # Extract high-confidence related notes
        threshold = self.config.MEMORY_CONFIDENCE_THRESHOLD
        suggested = [
            f"[[{r['note_id']}]]"
            for r in state["related_notes"]
            if r.get("score", 0) >= threshold
        ]

        state["suggested_links"] = suggested

        if suggested:
            logger.info(f"Generated {len(suggested)} link suggestions")
        else:
            logger.info("No high-confidence links generated")

        return state

    async def _store_memory(self, state: BrainState) -> BrainState:
        """Store the new note in Mem0 for future retrieval."""
        logger.info("Storing note in semantic memory...")

        # Build metadata
        metadata = {
            "category": state["category"],
            "suggested_links": state["suggested_links"],
            "related_count": len(state["related_notes"]),
            **state.get("metadata", {}),
        }

        # Add to Mem0
        memory_id = await self.memory_client.add_note_memory(
            note_id=state.get("note_id", "unknown"),
            category=state["category"],
            content=state["input_note"],
            metadata=metadata,
        )

        logger.info(f"Stored memory with ID: {memory_id}")
        return state

    async def process_note(
        self,
        input_note: str,
        category: str,
        note_id: Optional[str] = None,
        extracted_fields: Optional[Dict[str, Any]] = None,
    ) -> BrainState:
        """
        Process a note through the memory-aware pipeline.

        Args:
            input_note: The raw note content
            category: The note category
            note_id: The database record ID
            extracted_fields: Fields extracted by the classifier

        Returns:
            The final brain state with memories and suggestions
        """
        initial_state: BrainState = {
            "input_note": input_note,
            "category": category,
            "note_id": note_id,
            "extracted_fields": extracted_fields or {},
            "relevant_memories": [],
            "related_notes": [],
            "suggested_links": [],
            "enhanced_note": None,
            "metadata": {"processed_at": datetime.now().isoformat()},
        }

        # Run through the graph
        final_state = await self.graph.ainvoke(initial_state)

        return final_state

    async def extract_insights(
        self,
        notes: List[Dict[str, Any]],
        focus_area: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract high-level insights from a collection of notes.

        Used for weekly reflection and pattern detection.

        Args:
            notes: List of notes to analyze
            focus_area: Optional focus area (category or theme)

        Returns:
            Insights including patterns, themes, and connections
        """
        logger.info(f"Extracting insights from {len(notes)} notes...")

        # This would use an LLM call to analyze patterns
        # For now, we return a structured placeholder
        llm_client = self.config.get_llm_client()

        # Format notes for LLM
        notes_text = "\n\n".join([
            f"[{n.get('category', 'unknown')}] {n.get('content', '')}"
            for n in notes[:50]  # Limit to 50 notes
        ])

        prompt = f"""Analyze these notes and extract:
1. Recurring themes or topics
2. Connections between notes
3. Emerging patterns
4. Key entities or concepts
5. Action items or follow-ups

Notes:
{notes_text}

{"Focus on: " + focus_area if focus_area else ""}

Provide a structured JSON response with these sections."""

        try:
            result = await llm_client.complete_json(
                prompt=prompt,
                temperature=0.5,
                max_tokens=1000,
            )

            logger.info("Insights extracted successfully")
            return result

        except Exception as e:
            logger.error(f"Failed to extract insights: {e}")
            return {
                "themes": [],
                "connections": [],
                "patterns": [],
                "entities": [],
                "actions": [],
            }


# Singleton instance
_brain: Optional[MemoryBrain] = None


def get_brain() -> MemoryBrain:
    """Get the singleton memory brain."""
    global _brain
    if _brain is None:
        _brain = MemoryBrain()
    return _brain
```

---

### 2.4 Memory Enhancement Prompt

**File:** `prompts/memory.md`

Create prompts for memory extraction and analysis:

```markdown
# Memory Extraction and Enhancement

You are a memory extraction system for a personal knowledge base.

Your task is to analyze incoming notes and:
1. Extract discrete facts and knowledge
2. Identify relationships with previous notes
3. Suggest connections and links
4. Detect patterns and themes

## Input Context

- Current Note: {input_note}
- Category: {category}
- Relevant Memories: {relevant_memories}
- Related Notes: {related_notes}

## Your Responsibilities

### 1. Fact Extraction
Extract atomic facts from the note. Each fact should be:
- Standalone and meaningful
- Contextually complete
- Useful for future retrieval

Examples:
- "User is researching Rust memory management"
- "LangGraph is used for agent orchestration"
- "Project 'website redesign' is in active status"

### 2. Relationship Detection
Identify how this note relates to:
- Previous notes on similar topics
- Ongoing projects or tasks
- People or decisions mentioned
- Reference material (decisions, howtos, snippets)

### 3. Link Suggestions
Suggest internal links using the format: `[[note_id]]`

Only suggest links when:
- Semantic similarity > 0.7
- The connection is meaningful and useful
- The related note adds context

### 4. Pattern Recognition
Identify patterns such as:
- Recurring themes across notes
- Evolving ideas or decisions
- Clusters of related activity
- Unresolved threads

## Output Format

Return a JSON object with:

```json
{
  "facts": ["fact1", "fact2", ...],
  "relationships": [
    {"type": "related_to|builds_on|contradicts|references", "note_id": "...", "reason": "..."}
  ],
  "suggested_links": ["[[id1]]", "[[id2]]"],
  "patterns": ["pattern1", "pattern2"],
  "metadata": {
    "key_entities": ["entity1", "entity2"],
    "topics": ["topic1", "topic2"]
  }
}
```
```

---

## Phase 3: Integration with Existing System

### 3.1 Router Enhancement

**File:** `bot/router.py`

Modify the router to integrate with the memory layer:

```python
# Add imports
import asyncio
from memory.mem0_client import get_memory_client
from memory.graph import get_brain

# After successful note storage, add to memory
async def route_message(...) -> Tuple[Optional[str], Optional[str], Optional[float], str]:
    # ... existing routing logic ...

    if status == "filed" and record_id:
        # Enhance with memory layer (run in background)
        asyncio.create_task(
            _enhance_with_memory(
                text=text,
                category=category,
                record_id=record_id,
                extracted=extracted,
            )
        )

    return category, record_id, confidence, "filed"


async def _enhance_with_memory(
    text: str,
    category: str,
    record_id: str,
    extracted: dict,
):
    """Background task to add memory layer processing."""
    try:
        brain = get_brain()
        await brain.process_note(
            input_note=text,
            category=category,
            note_id=record_id,
            extracted_fields=extracted,
        )
    except Exception as e:
        logger.error(f"Memory enhancement failed: {e}")
```

---

### 3.2 Smart Linking in Queries

**File:** `bot/commands.py`

Enhance query commands to use semantic search:

```python
async def handle_command(command: str, arg: str) -> str:
    # ... existing logic ...

    # Add semantic memory search
    if command == "semsearch":  # New command
        return await _semantic_search(arg)

    # ... existing commands ...


async def _semantic_search(query: str) -> str:
    """Semantic search using Mem0."""
    from memory.mem0_client import get_memory_client

    memory_client = get_memory_client()
    memories = await memory_client.search_relevant_context(query)

    if not memories:
        return "No relevant memories found."

    lines = ["🧠 Relevant Memories:\n"]
    for m in memories:
        metadata = m.get("metadata", {})
        lines.append(
            f"• {m['memory']}\n"
            f"  (from {metadata.get('category', 'unknown')} note {metadata.get('note_id', 'N/A')})"
        )

    return "\n".join(lines)
```

---

## Phase 4: Bootstrap and Migration

### 4.1 Bootstrap Script

**File:** `scripts/bootstrap_memory.py`

Create a script to migrate existing notes to Mem0:

```python
#!/usr/bin/env python3
"""
Bootstrap Mem0 with existing notes from PostgreSQL.

Usage:
    python scripts/bootstrap_memory.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from config import Config
from db import get_pool, close_pool
from memory.mem0_client import get_memory_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def bootstrap_category(table: str, category: str):
    """Bootstrap all records from a category."""
    pool = await get_pool()
    memory_client = get_memory_client()

    async with pool.acquire() as conn:
        rows = await conn.fetch(f"SELECT * FROM {table}")

        logger.info(f"Bootstrapping {len(rows)} records from {table}...")

        for i, row in enumerate(rows, 1):
            record = dict(row)
            record_id = str(record["id"])

            # Build content from record fields
            content_parts = []
            for key, value in record.items():
                if key not in ["id", "created_at", "updated_at"] and value:
                    content_parts.append(f"{key}: {value}")

            content = " | ".join(content_parts)

            # Build metadata
            metadata = {
                "bootstrapped": True,
                "bootstrapped_at": __import__("datetime").datetime.now().isoformat(),
            }

            # Add to memory
            try:
                await memory_client.add_note_memory(
                    note_id=record_id,
                    category=category,
                    content=content,
                    metadata=metadata,
                )
                logger.info(f"[{i}/{len(rows)}] Added {category}/{record_id}")
            except Exception as e:
                logger.error(f"Failed to add {category}/{record_id}: {e}")

        logger.info(f"Completed bootstrapping {table}")


async def main():
    logger.info("Starting memory bootstrap...")

    # Validate configuration
    from memory.config import MemoryConfig
    missing = MemoryConfig.validate()
    if missing:
        logger.error(f"Missing configuration: {', '.join(missing)}")
        sys.exit(1)

    # Categories to bootstrap
    categories = [
        ("people", "people"),
        ("projects", "projects"),
        ("ideas", "ideas"),
        ("admin", "admin"),
        ("decisions", "decisions"),
        ("howtos", "howtos"),
        ("snippets", "snippets"),
    ]

    for table, category in categories:
        await bootstrap_category(table, category)

    logger.info("Memory bootstrap complete!")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Phase 5: Weekly Reflection

### 5.1 Reflection Script

**File:** `scripts/reflection.py`

Create the weekly reflection script:

```python
#!/usr/bin/env python3
"""
Weekly reflection cron job.
Run at Sunday 16:00.

Analyzes recent notes and generates insights.

Usage:
    python scripts/reflection.py
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from telegram import Bot
from config import Config
from db import get_pool, close_pool
from memory.graph import get_brain
from memory.mem0_client import get_memory_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def get_weekly_notes():
    """Get all notes from the past week."""
    pool = await get_pool()
    cutoff = datetime.now() - timedelta(days=7)

    notes = []

    async with pool.acquire() as conn:
        for table in ["people", "projects", "ideas", "admin"]:
            rows = await conn.fetch(
                f"""
                SELECT * FROM {table}
                WHERE created_at >= $1
                ORDER BY created_at DESC
                """,
                cutoff,
            )
            for row in rows:
                r = dict(row)
                r["category"] = table
                notes.append(r)

    logger.info(f"Found {len(notes)} notes from the past week")
    return notes


async def generate_reflection(notes):
    """Generate weekly reflection using LangGraph."""
    brain = get_brain()

    insights = await brain.extract_insights(notes)

    return insights


async def save_reflection_to_db(insights: dict) -> str:
    """Save the reflection as an idea in the database."""
    from db import insert_record

    title = f"Weekly Reflection - {datetime.now().strftime('%Y-%m-%d')}"

    # Format insights as elaboration
    elaboration_parts = []
    for section, items in insights.items():
        if items:
            elaboration_parts.append(f"**{section.title()}**\n" + "\n".join(f"- {i}" for i in items))

    elaboration = "\n\n".join(elaboration_parts)

    record_id = await insert_record(
        "ideas",
        {
            "title": title,
            "one_liner": f"Reflection on the past week's notes ({len(insights.get('themes', []))} themes found)",
            "elaboration": elaboration,
        },
    )

    return record_id


async def send_reflection_to_telegram(bot: Bot, chat_id: int, insights: dict, note_id: str):
    """Send the reflection via Telegram."""
    lines = [
        "🧠 **Weekly Reflection**",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    for section, items in insights.items():
        if items:
            lines.append(f"**{section.title()}**")
            for item in items[:5]:  # Limit to 5 per section
                lines.append(f"• {item}")
            lines.append("")

    lines.append(f"💾 Saved as idea: [[{note_id}]]")

    message = "\n".join(lines)

    # Handle long messages
    if len(message) > 4000:
        message = message[:3970] + "\n... (truncated)"

    await bot.send_message(chat_id=chat_id, text=message)


async def main():
    logger.info("Starting weekly reflection...")

    if not Config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    # Validate memory config
    from memory.config import MemoryConfig
    missing = MemoryConfig.validate()
    if missing:
        logger.error(f"Missing configuration: {', '.join(missing)}")
        sys.exit(1)

    bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)

    try:
        # Get weekly notes
        notes = await get_weekly_notes()

        if not notes:
            logger.info("No notes from the past week to reflect on")
            return

        # Generate insights
        logger.info("Generating insights...")
        insights = await generate_reflection(notes)
        logger.info(f"Insights generated: {list(insights.keys())}")

        # Save to database
        note_id = await save_reflection_to_db(insights)
        logger.info(f"Reflection saved as idea {note_id}")

        # Send via Telegram
        await send_reflection_to_telegram(bot, Config.TELEGRAM_OWNER_ID, insights, note_id)
        logger.info("Weekly reflection sent successfully")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Phase 6: Testing and Validation

### 6.1 Unit Tests

**File:** `tests/unit/test_memory.py`

```python
"""Unit tests for memory layer."""

import pytest
from memory.mem0_client import LeaknoteMemory
from memory.graph import MemoryBrain


@pytest.mark.asyncio
async def test_add_and_search_memory():
    """Test adding and searching memories."""
    client = LeaknoteMemory()

    # Add a memory
    memory_id = await client.add_note_memory(
        note_id="test-1",
        category="ideas",
        content="Test idea about Rust programming",
    )

    assert memory_id

    # Search for it
    results = await client.search_relevant_context("Rust programming")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_brain_processing():
    """Test the LangGraph brain processing."""
    brain = MemoryBrain()

    result = await brain.process_note(
        input_note="I should learn more about LangGraph for agent orchestration",
        category="ideas",
        note_id="test-2",
    )

    assert result["category"] == "ideas"
    assert "suggested_links" in result
```

---

## Summary of Changes

### Files Created (Phase 1 & 2)

1. `memory/__init__.py` - Package init ✅
2. `memory/config.py` - Memory layer configuration ✅
3. `memory/mem0_client.py` - Mem0 wrapper ✅
4. `memory/graph.py` - LangGraph orchestration ✅
5. `prompts/memory.md` - Memory extraction prompt ✅

### Files Modified (Phase 1)

1. `docker-compose.yml` - Add Qdrant service ✅
2. `requirements.txt` - Add dependencies ✅
3. `.env.example` - Add configuration variables ✅

### Files Pending (Phase 3+)

4. `bot/router.py` - Integrate memory processing (pending)
5. `bot/commands.py` - Add semantic search command (pending)
6. `bot/main.py` - Add new help command for `?semsearch` (pending)
7. `scripts/bootstrap_memory.py` - Migration script (pending)
8. `scripts/reflection.py` - Weekly reflection (pending)
9. `tests/unit/test_memory.py` - Memory tests (pending)

### Environment Variables Added (Phase 1)

- `QDRANT_URL` - Qdrant connection URL ✅
- `MEMORY_PROVIDER` - Memory LLM provider ✅
- `MEMORY_API_URL` - Memory LLM API URL ✅
- `MEMORY_API_KEY` - Memory LLM API key ✅
- `MEMORY_MODEL` - Memory LLM model ✅
- `MEM0_COLLECTION` - Qdrant collection name ✅
- `MEMORY_RETRIEVAL_LIMIT` - Number of memories to retrieve ✅
- `MEMORY_CONFIDENCE_THRESHOLD` - Minimum similarity for links ✅

---

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Complete | Infrastructure Setup (Qdrant, dependencies, config) |
| 2 | ✅ Complete | Memory Layer Implementation (Mem0, LangGraph, prompts) |
| 3 | Pending | Integration with Existing System (router, commands) |
| 4 | Pending | Bootstrap and Migration Scripts |
| 5 | Pending | Weekly Reflection Script |
| 6 | Pending | Testing and Validation |

---

## Next Steps

1. ✅ ~~Review and approve this plan~~ - Plan reviewed, Phases 1 & 2 complete
2. ✅ ~~Create the `memory/` directory structure~~ - Complete
3. ✅ ~~Implement files in order (Phase 1 → Phase 6)~~ - Phases 1 & 2 complete
4. **Phase 3: Integrate with bot/router.py** - Add memory enhancement background task
5. **Phase 3: Add semantic search command** - Update bot/commands.py
6. **Phase 4: Create bootstrap script** - Migrate existing notes to Mem0
7. **Phase 5: Create reflection script** - Weekly pattern detection
8. **Phase 6: Add unit tests** - Test memory layer functionality
9. Test with a small subset of notes first
10. Run bootstrap script on full database
11. Monitor weekly reflections
12. Iterate based on usage patterns
