"""Factory de LangChain ChatModels con soporte para vLLM, Ollama, y LoRA adapters.

Separa la creación de modelos LangChain (para DeepAgents) del LLM HTTP client
que usamos para embeddings y otros usos.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from src.core.config import settings
from src.core.logging import logging

logger = logging.getLogger(__name__)


def create_vllm_chat_model(
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str = "dummy",
    adapter: str | None = None,
    temperature: float = 0.7,
    streaming: bool = True,
) -> ChatOpenAI:
    """Create a ChatOpenAI pointing to our vLLM OpenAI-compatible server.

    For LoRA adapters, vLLM exposes them via the model name field.
    Format: "base_model:adapter_name" (vLLM 0.5+).
    """
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
) -> ChatOllama:
    """Create a ChatOllama pointing to our Ollama server."""
    model = model_name or settings.OLLAMA_MODEL
    base_url = base_url or settings.OLLAMA_BASE_URL.replace("/v1", "")

    if adapter:
        model = f"{model}:{adapter}"
        logger.info("Using Ollama adapter: %s", model)

    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature,
        streaming=streaming,
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
