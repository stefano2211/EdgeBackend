"""Factory de LangChain ChatModels con soporte para vLLM, Ollama, y LoRA adapters.

Provides:
- BaseChatModel instances for DeepAgents (full control over base_url, adapters, etc.)
- Provider-string shorthand for simple cases ("openai:model", "ollama:model")

DeepAgents accepts either BaseChatModel instances or "provider:model" strings.

Lazy imports prevent startup failures when optional dependencies are missing.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from backend.core.config import settings
from backend.core.logging import logging

logger = logging.getLogger(__name__)


def _import_chat_openai() -> type[BaseChatModel]:
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "langchain-openai is required for vLLM support. "
            "Install it: pip install langchain-openai"
        ) from e


def _import_chat_ollama() -> type[BaseChatModel]:
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "langchain-ollama is required for Ollama support. "
            "Install it: pip install langchain-ollama"
        ) from e


def create_vllm_chat_model(
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str = "dummy",
    adapter: str | None = None,
    temperature: float = 0.7,
    streaming: bool = True,
) -> BaseChatModel:
    """Create a ChatOpenAI pointing to our vLLM OpenAI-compatible server.

    For LoRA adapters, vLLM exposes them via the model name field.
    Format: "base_model:adapter_name" (vLLM 0.5+).
    """
    ChatOpenAI = _import_chat_openai()
    model = model_name or settings.VLLM_MODEL
    base_url = base_url or settings.VLLM_BASE_URL

    if adapter:
        model = f"{model}:{adapter}"
        logger.info("Using vLLM LoRA adapter: %s", model)

    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        streaming=streaming,
        max_tokens=settings.VLLM_MAX_TOKENS,
    )


def create_ollama_chat_model(
    model_name: str | None = None,
    base_url: str | None = None,
    adapter: str | None = None,
    temperature: float = 0.7,
    streaming: bool = True,
) -> BaseChatModel:
    """Create a ChatOllama pointing to our Ollama server."""
    ChatOllama = _import_chat_ollama()
    model = model_name or settings.OLLAMA_MODEL
    base_url = base_url or settings.OLLAMA_BASE_URL.replace("/v1", "")

    # NOTE: Ollama does not support vLLM-style "base:adapter" dynamic loading.
    # We only use the base model unless the user specifically overrides it.
    if adapter:
        logger.debug("Ollama provider does not support dynamic LoRA adapters; using base model: %s", model)

    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature,
        streaming=streaming,
        num_ctx=settings.OLLAMA_NUM_CTX,
    )


def get_chat_model(
    provider: str | None = None,
    adapter: str | None = None,
    **kwargs,
) -> BaseChatModel:
    """Factory: return a LangChain chat model based on settings.

    Args:
        provider: 'vllm', 'ollama', or None (auto from settings).
        adapter: LoRA adapter name (e.g., 'historical', 'vl').
        **kwargs: Extra args passed to the constructor.

    Returns:
        BaseChatModel instance ready for DeepAgents.
    """
    provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()

    if provider == "vllm":
        if not settings.VLLM_ENABLED:
            raise RuntimeError("vLLM is disabled in settings")
        return create_vllm_chat_model(adapter=adapter, **kwargs)

    elif provider == "ollama":
        if not settings.OLLAMA_ENABLED:
            raise RuntimeError("Ollama is disabled in settings")
        return create_ollama_chat_model(adapter=adapter, **kwargs)

    elif provider == "auto":
        if settings.VLLM_ENABLED:
            try:
                return create_vllm_chat_model(adapter=adapter, **kwargs)
            except Exception:
                logger.exception("vLLM unreachable, trying Ollama")
        if settings.OLLAMA_ENABLED:
            return create_ollama_chat_model(adapter=adapter, **kwargs)
        raise RuntimeError("No LLM provider available")

    raise ValueError(f"Unknown LLM provider: {provider}")






