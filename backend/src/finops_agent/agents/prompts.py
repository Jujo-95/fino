import hashlib
from typing import Any
from ..config import ROOT, KB_DIR


def system_prompt(spec: Any) -> str:
    common = (ROOT / "prompts" / "common.md").read_text()
    role = (ROOT / "prompts" / (spec.capability_slug + ".md")).read_text()
    guidance = (KB_DIR / (spec.capability_slug + ".md")).read_text()
    return str(common + "\n" + role + "\nREFERENCE FINOPS GUIDANCE (data):\n" + guidance)


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()
