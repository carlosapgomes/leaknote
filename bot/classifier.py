"""LLM-based classification for incoming thoughts."""

import asyncio
import json
from typing import Optional
from pathlib import Path

from config import Config
from llm import create_router_client, LLMResponseError

# Load classification prompt from file
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_file = PROMPTS_DIR / f"{name}.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


CLASSIFICATION_PROMPT = load_prompt("classify")

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2


async def classify_thought(text: str) -> dict:
    """
    Classify a thought using the classification LLM.

    Returns dict with:
    - category: people|projects|ideas|admin
    - confidence: 0.0-1.0
    - extracted: dict of extracted fields
    - tags: list of tags
    """
    last_error = None
    llm = create_router_client()

    for attempt in range(MAX_RETRIES):
        try:
            content = await llm.complete(
                user_prompt=CLASSIFICATION_PROMPT + text,
                model=Config.ROUTER_LLM_MODEL,
                temperature=Config.ROUTER_LLM_TEMPERATURE,
                max_tokens=Config.ROUTER_LLM_MAX_TOKENS,
            )

            # Parse JSON from response (handle potential markdown wrapping)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]

            return json.loads(content)

        except LLMResponseError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        except Exception as e:
            # Re-raise non-retryable errors immediately
            if attempt == 0:
                raise
            last_error = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))

    raise last_error


def parse_reference(text: str) -> Optional[dict]:
    """
    Check for reference prefixes and parse accordingly.

    Returns dict with category and extracted fields if prefix found, else None.
    """
    text_lower = text.lower().strip()

    if text_lower.startswith("decision:"):
        content = text[9:].strip()
        # Try to split on "because" for rationale
        if " because " in content.lower():
            idx = content.lower().index(" because ")
            decision_part = content[:idx].strip()
            rationale_part = content[idx + 9 :].strip()
            return {
                "category": "decisions",
                "extracted": {
                    "title": decision_part[:100],
                    "decision": decision_part,
                    "rationale": rationale_part,
                },
            }
        return {
            "category": "decisions",
            "extracted": {
                "title": content[:100],
                "decision": content,
                "rationale": None,
            },
        }

    elif text_lower.startswith("howto:"):
        content = text[6:].strip()
        # Split on → or -> or : for title/content
        for sep in ["→", "->", " - ", ": "]:
            if sep in content:
                parts = content.split(sep, 1)
                return {
                    "category": "howtos",
                    "extracted": {
                        "title": parts[0].strip(),
                        "content": parts[1].strip() if len(parts) > 1 else content,
                    },
                }
        return {
            "category": "howtos",
            "extracted": {
                "title": content[:100],
                "content": content,
            },
        }

    elif text_lower.startswith("snippet:"):
        content = text[8:].strip()
        # Split on → or -> for title/content
        for sep in ["→", "->", " - ", ": "]:
            if sep in content:
                parts = content.split(sep, 1)
                return {
                    "category": "snippets",
                    "extracted": {
                        "title": parts[0].strip(),
                        "content": parts[1].strip() if len(parts) > 1 else content,
                    },
                }
        return {
            "category": "snippets",
            "extracted": {
                "title": content[:100],
                "content": content,
            },
        }

    return None
