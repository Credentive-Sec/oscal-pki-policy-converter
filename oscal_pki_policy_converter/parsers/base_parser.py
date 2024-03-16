from oscal_pydantic import document
from typing import Any

class AbstractParser:
    def policy_to_catalog(self, parse_config: dict[str, Any], policy_text: list[str]) -> document.Document:
        # This function call returns an empty OSCAL document - it shouldn't be used
        return document.Document(
            catalog=None,
        )