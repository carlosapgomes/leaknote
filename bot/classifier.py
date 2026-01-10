"""LLM-based classification for incoming thoughts."""

import asyncio
import json
import httpx
from typing import Optional
from pathlib import Path

from config import Config

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
    Classify a thought using the classification LLM (GLM-4).

    Returns dict with:
    - category: people|projects|ideas|admin
    - confidence: 0.0-1.0
    - extracted: dict of extracted fields
    - tags: list of tags
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    Config.GLM_API_URL,
                    headers={
                        "Authorization": f"Bearer {Config.GLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": Config.GLM_MODEL,
                        "messages": [
                            {"role": "user", "content": CLASSIFICATION_PROMPT + text}
                        ],
                        "temperature": 0.1,  # Low for consistent classification
                    },
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Parse JSON from response (handle potential markdown wrapping)
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0]

                return json.loads(content)

        except httpx.TimeoutException as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise
        except json.JSONDecodeError as e:
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
