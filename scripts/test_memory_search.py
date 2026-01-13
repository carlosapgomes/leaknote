#!/usr/bin/env python3
"""Test semantic memory search from command line."""

import asyncio
import sys
import logging
from memory.mem0_client import get_memory_client

# Enable debug logging
logging.basicConfig(level=logging.INFO)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_memory_search.py '<query>'")
        print("Example: python scripts/test_memory_search.py 'eqmd'")
        sys.exit(1)

    query = sys.argv[1]
    print(f"Searching for: {query}\n")

    memory_client = get_memory_client()

    # First, let's try to get all memories to see what's stored
    print("=== Checking all memories in database ===")
    try:
        all_result = memory_client.memory.get_all(user_id="leaknote_user")
        # mem0 returns {"results": [...]}
        if isinstance(all_result, dict):
            all_memories = all_result.get("results", [])
        else:
            all_memories = all_result

        print(f"Total memories stored: {len(all_memories)}\n")
        if all_memories:
            print("Sample memories:")
            for m in all_memories[:3]:
                print(f"  - {m}\n")
    except Exception as e:
        print(f"Error getting all memories: {e}\n")

    print("=== Now performing semantic search ===")
    try:
        memories = await memory_client.search_relevant_context(query, limit=10)

        if not memories:
            print("No memories found from semantic search.")
        else:
            print(f"Found {len(memories)} memories:\n")
            for m in memories:
                metadata = m.get("metadata", {})
                category = metadata.get("category", "unknown")
                note_id = metadata.get("note_id", "N/A")
                score = m.get("score", 0.0)

                print(f"• {m['memory']}")
                print(f"  (from {category}/{note_id}, relevance: {score:.2f})")
                print()
    except Exception as e:
        print(f"Error during search: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
