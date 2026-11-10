"""Legacy import compatibility; runtime uses structured documents, not HippoRAG."""
from .context_store import ClientContextStore as DualHippoRAGService

__all__ = ["DualHippoRAGService"]
