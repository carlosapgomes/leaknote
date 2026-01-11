"""LLM-based classification for incoming thoughts."""

from typing import Optional
from pathlib import Path

from bot.config import Config

# Load classification prompt from file
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_file = PROMPTS_DIR / f"{name}.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


CLASSIFICATION_PROMPT = load_prompt("classify")


async def classify_thought(text: str) -> dict:
    """
    Classify a thought using the classification LLM.

    Returns dict with:
    - category: people|projects|ideas|admin
    - confidence: 0.0-1.0
    - extracted: dict of extracted fields
    - tags: list of tags
    """
    import logging
    logger = logging.getLogger(__name__)

    client = Config.get_classify_client()

    # Use complete_json for structured output
    # Note: GPT-5 only supports temperature=1
    result = await client.complete_json(
        prompt=CLASSIFICATION_PROMPT + text,
        temperature=1.0,
        max_tokens=500,
    )

    logger.info(f"Classification result: {result}")
    return result


def parse_reference(text: str) -> Optional[dict]:
    """
    Check for reference prefixes and parse accordingly.

    Returns dict with category and extracted fields if prefix found, else None.
    """
    text_lower = text.lower().strip()

    if text_lower.startswith("idea:"):
        content = text[5:].strip()
        return {
            "category": "ideas",
            "extracted": {
                "title": content[:100],
                "one_liner": content[:200],
                "elaboration": content,
            },
        }

    elif text_lower.startswith("person:"):
        content = text[7:].strip()
        return {
            "category": "people",
            "extracted": {
                "name": content[:100],
                "context": content,
                "follow_ups": None,
            },
        }

    elif text_lower.startswith("project:"):
        content = text[8:].strip()
        return {
            "category": "projects",
            "extracted": {
                "name": content[:100],
                "status": "active",
                "next_action": content,
                "notes": content,
            },
        }

    elif text_lower.startswith("admin:"):
        content = text[6:].strip()
        return {
            "category": "admin",
            "extracted": {
                "name": content[:100],
                "due_date": None,
                "notes": content,
            },
        }

    elif text_lower.startswith("decision:"):
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
