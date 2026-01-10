"""Handle fix commands to correct misclassifications."""

import re
from typing import Optional, Tuple

from db import (
    get_inbox_log_by_event,
    get_record,
    delete_record,
    insert_record,
    update_inbox_log,
)
from classifier import classify_thought, parse_reference
from router import CATEGORY_TABLE_MAP, CATEGORY_DISPLAY


# Valid categories for fix command
VALID_CATEGORIES = {
    "person": "people",
    "people": "people",
    "project": "projects",
    "projects": "projects",
    "idea": "ideas",
    "ideas": "ideas",
    "admin": "admin",
    "decision": "decisions",
    "decisions": "decisions",
    "howto": "howtos",
    "howtos": "howtos",
    "snippet": "snippets",
    "snippets": "snippets",
}


def parse_fix_command(text: str) -> Optional[str]:
    """
    Parse a fix command from message text.
    Returns the target category (table name) or None if not a fix command.

    Formats:
    - fix: people
    - fix: person
    - fix:project
    """
    text = text.strip().lower()

    # Match "fix:" followed by category
    match = re.match(r"^fix:\s*(\w+)", text)
    if not match:
        return None

    category_input = match.group(1)
    return VALID_CATEGORIES.get(category_input)


async def handle_fix(
    original_event_id: str,
    new_category: str,
) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Handle a fix command.

    Returns: (success, message, old_category, extracted_name)
    """

    # Get the original inbox log entry
    log_entry = await get_inbox_log_by_event(original_event_id)
    if not log_entry:
        return False, "Couldn't find the original message to fix", None, None

    old_category = log_entry["destination"]
    old_record_id = log_entry["record_id"]
    raw_text = log_entry["raw_text"]

    # If same category, nothing to do
    if old_category == new_category:
        display = CATEGORY_DISPLAY.get(new_category, new_category)
        return False, f"Already filed as {display}", None, None

    # Delete old record if it exists
    if old_record_id and old_category:
        await delete_record(old_category, str(old_record_id))

    # Re-classify for the new category
    if new_category in ("decisions", "howtos", "snippets"):
        # Reference categories need the prefix - add it and re-parse
        prefix_map = {
            "decisions": "decision:",
            "howtos": "howto:",
            "snippets": "snippet:",
        }
        prefixed_text = f"{prefix_map[new_category]} {raw_text}"

        ref_result = parse_reference(prefixed_text)

        if ref_result:
            extracted = ref_result["extracted"]
            new_record_id = await insert_record(new_category, extracted)
            extracted_name = (
                extracted.get("title") or extracted.get("name") or raw_text[:50]
            )
        else:
            return False, "Couldn't parse as reference", None, None
    else:
        # Dynamic category - use prefix-based extraction for the target category
        # Map table names to their prefixes
        prefix_map = {
            "people": "person:",
            "projects": "project:",
            "ideas": "idea:",
            "admin": "admin:",
        }

        prefix = prefix_map.get(new_category, "")
        prefixed_text = f"{prefix} {raw_text}"

        ref_result = parse_reference(prefixed_text)

        if ref_result:
            extracted = ref_result["extracted"]
            # Get tags from the original classification if available
            try:
                original_classification = await classify_thought(raw_text)
                tags = original_classification.get("tags", [])
                if tags:
                    extracted["tags"] = tags
            except Exception:
                pass  # Tags are optional, continue without them

            new_record_id = await insert_record(new_category, extracted)
            extracted_name = (
                extracted.get("name") or extracted.get("title") or raw_text[:50]
            )
        else:
            return False, f"Couldn't extract data for category '{new_category}'", None, None

    # Update inbox log
    await update_inbox_log(
        str(log_entry["id"]),
        {
            "destination": new_category,
            "record_id": new_record_id,
            "status": "fixed",
        },
    )

    old_display = CATEGORY_DISPLAY.get(old_category, old_category) if old_category else "unknown"
    return True, "Fixed", old_display, extracted_name
