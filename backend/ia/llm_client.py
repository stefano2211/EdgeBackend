"""Unified LLM client that supports vLLM and Ollama as backends."""

from typing import Any, AsyncIterator
import httpx
from backend.core.config import settings
from backend.core.logging import logging

logger = logging.getLogger(__name__)


class _ProviderConfig:
    __slots__ = ("name", "base_url", "model", "max_tokens", "api_key", "health_url")

    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        max_tokens: int,
        api_key: str | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.health_url = self._health_url()

    def _health_url(self) -> str:
        if self.name == "vllm":
            return self.base_url.replace("/v1", "") + "/health"
        return self.base_url.replace("/v1", "") + "/api/tags"


class LLMClient:
    """
    Unified client for LLM inference backends.

    Supports:
    - vLLM (OpenAI-compatible API)
    - Ollama (OpenAI-compatible endpoint)

    Auto-detection:
    - If DEFAULT_LLM_PROVIDER="auto" (default), probes both backends
      and selects the first one that responds (vLLM preferred over Ollama).
    - If set to "vllm" or "ollama", forces that provider.
    """

    def __init__(self) -> None:
        self.provider: str | None = None
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=120.0)
        self._cfg: _ProviderConfig | None = None

    async def init(self) -> None:
        """Must be called before first use to detect/lock the provider."""
        requested = settings.DEFAULT_LLM_PROVIDER.lower()

        if requested == "auto":
            cfg = await self._detect_provider()
            if cfg is None:
                raise RuntimeError(
                    "No LLM backend available. "
                    "Ensure either vLLM or Ollama is running and reachable."
                )
            self._cfg = cfg
            self.provider = cfg.name
        else:
            self._cfg = self._get_config_for(requested)
            self.provider = requested

        logger.info(
            "LLM client initialized | provider=%s model=%s url=%s",
            self.provider,
            self._cfg.model,
            self._cfg.base_url,
        )

    def _get_config_for(self, name: str) -> _ProviderConfig:
        if name == "vllm":
            if not settings.VLLM_ENABLED:
                raise RuntimeError("vLLM is forced but VLLM_ENABLED=False")
            return _ProviderConfig(
                name="vllm",
                base_url=settings.VLLM_BASE_URL,
                model=settings.VLLM_MODEL,
                max_tokens=settings.VLLM_MAX_TOKENS,
                api_key=settings.VLLM_API_KEY,
            )
        elif name == "ollama":
            if not settings.OLLAMA_ENABLED:
                raise RuntimeError("Ollama is forced but OLLAMA_ENABLED=False")
            return _ProviderConfig(
                name="ollama",
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                max_tokens=settings.OLLAMA_MAX_TOKENS,
            )
        raise ValueError(f"Unknown LLM provider: {name}")

    async def _detect_provider(self) -> _ProviderConfig | None:
        """Probe vLLM first (preferred), then Ollama."""
        candidates: list[_ProviderConfig] = []
        if settings.VLLM_ENABLED:
            candidates.append(
                _ProviderConfig(
                    name="vllm",
                    base_url=settings.VLLM_BASE_URL,
                    model=settings.VLLM_MODEL,
                    max_tokens=settings.VLLM_MAX_TOKENS,
                    api_key=settings.VLLM_API_KEY,
                )
            )
        if settings.OLLAMA_ENABLED:
            candidates.append(
                _ProviderConfig(
                    name="ollama",
                    base_url=settings.OLLAMA_BASE_URL,
                    model=settings.OLLAMA_MODEL,
                    max_tokens=settings.OLLAMA_MAX_TOKENS,
                )
            )

        for cfg in candidates:
            try:
                resp = await self._client.get(cfg.health_url, timeout=5.0)
                if resp.status_code == 200:
                    logger.info("Detected LLM backend: %s at %s", cfg.name, cfg.base_url)
                    return cfg
            except Exception:
                logger.debug("LLM backend not reachable: %s at %s", cfg.name, cfg.base_url)
                continue

        return None

    @property
    def base_url(self) -> str:
        if self._cfg is None:
            raise RuntimeError("LLMClient not initialized. Call await client.init() first.")
        return self._cfg.base_url

    @property
    def model(self) -> str:
        if self._cfg is None:
            raise RuntimeError("LLMClient not initialized. Call await client.init() first.")
        return self._cfg.model

    @property
    def max_tokens(self) -> int:
        if self._cfg is None:
            raise RuntimeError("LLMClient not initialized. Call await client.init() first.")
        return self._cfg.max_tokens

    @property
    def api_key(self) -> str | None:
        if self._cfg is None:
            raise RuntimeError("LLMClient not initialized. Call await client.init() first.")
        return self._cfg.api_key

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        images: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """
        Send a chat completion request to the active backend.

        Args:
            images: List of base64-encoded image strings. For Ollama multimodal models,
                    these are attached to the last user message.

        Returns the full response dict if stream=False,
        or an async iterator of chunks if stream=True.
        """
        # Clonar mensajes para no mutar el original
        msgs = list(messages)

        # Multimodal: adjuntar imágenes al último mensaje del usuario
        if images and self.provider == "ollama":
            # Encontrar el último mensaje de usuario
            for i in range(len(msgs) - 1, -1, -1):
                if msgs[i].get("role") == "user":
                    msgs[i] = dict(msgs[i])
                    msgs[i]["images"] = images
                    break

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        payload.update(kwargs)

        url = f"{self.base_url}/chat/completions"

        if stream:
            return self._stream_chat(url, payload)

        resp = await self._client.post(url, headers=self._headers(), json=payload)
        resp.raise_for_status()
        return resp.json()

    async def _stream_chat(
        self, url: str, payload: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        async with self._client.stream(
            "POST", url, headers=self._headers(), json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    import json
                    try:
                        yield json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

    async def embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for a list of texts.
        Falls back to sentence-transformers if the LLM backend doesn't support it.
        """
        # vLLM and Ollama OpenAI endpoints may not expose embeddings for all models.
        # For production, use a dedicated embedding model via sentence-transformers.
        # This is a placeholder that delegates to the embeddings utility.
        from backend.persistencia.vector.embeddings import get_embeddings
        return await get_embeddings(texts)

    async def health(self) -> bool:
        """Check if the LLM backend is reachable."""
        if self._cfg is None:
            return False
        try:
            resp = await self._client.get(self._cfg.health_url, timeout=10.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()


# Global singleton — use get_llm_client() after lifespan init
_llm_client: LLMClient | None = None


async def init_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
        await _llm_client.init()
    return _llm_client


def get_llm_client() -> LLMClient:
    if _llm_client is None:
        raise RuntimeError(
            "LLMClient not initialized. Ensure app lifespan has run init_llm_client()."
        )
    return _llm_client
