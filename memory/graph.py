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
