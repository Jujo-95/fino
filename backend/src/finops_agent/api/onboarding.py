"""Compatibility endpoint backed by the shared consulting diagnosis."""
from typing import Any
from ..consulting.diagnosis import diagnosis


def readiness(client: Any) -> dict[str, Any]:
    return diagnosis(client)
