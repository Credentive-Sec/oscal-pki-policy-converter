from oscal_pydantic import document

class AbstractParser:
    def policy_to_catalog(self, policy: list[str] = []) -> document.Document:
        # This function call returns an empty OSCAL document - it shouldn't be used
        return document.Document(
            catalog=None,
        )