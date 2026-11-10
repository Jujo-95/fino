import importlib
import os
from .nvidia import NvidiaProvider, settings
from typing import Any


class LLMProviderFactory:
    """NVIDIA by default; offline rules require explicit provider=mock."""
    @staticmethod
    def create() -> Any:
        provider = settings().get("FINOPS_LLM_PROVIDER", "nvidia")
        if provider == "nvidia":
            return NvidiaProvider()
        if provider in ("gemini","vertex"):
            from .gemini import GeminiProvider
            return GeminiProvider()
        if provider == "groq":
            from .groq_provider import GroqProvider
            return GroqProvider()
        if provider == "mock":
            return None
        model = os.getenv("FINOPS_LLM_MODEL")
        if not model:
            raise ValueError("FINOPS_LLM_MODEL is required for external providers")
        providers = {"openai": ("langchain_openai", "ChatOpenAI"),
                     "anthropic": ("langchain_anthropic", "ChatAnthropic")}
        if provider not in providers:
            raise ValueError("Unsupported LLM provider")
        module, name = providers[provider]
        return getattr(importlib.import_module(module), name)(model=model, temperature=0)
