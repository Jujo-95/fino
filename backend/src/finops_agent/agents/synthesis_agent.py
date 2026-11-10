"""Optional refinement hook retained for native specialist compatibility."""
from typing import Any
from langchain_core.tools import tool


def refinement_tool() -> Any:
    @tool
    def request_refinement() -> dict[str, str]:
        """Requesting refinement is disabled in the canonical analysis path."""
        return {'status': 'disabled', 'message': 'La refinación se realiza en el siguiente análisis canónico.'}
    return request_refinement
