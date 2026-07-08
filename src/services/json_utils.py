import json
import re
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("AI response did not contain a JSON object.")
        value = json.loads(match.group(0))

    if not isinstance(value, dict):
        raise ValueError("AI response JSON is not an object.")
    return value
