"""get_secret_credential — LangChain tool for sub-agents to retrieve stored secrets.

The VL Agent or Industrial Agent calls this tool when they encounter a login
screen or need an API key.  The tool decrypts the credential on-the-fly from
the database, so the plaintext never appears in system prompts.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from backend.core.logging import logging

logger = logging.getLogger(__name__)


class _GetSecretArgs(BaseModel):
    key_identifier: str = Field(
        ...,
        description=(
            "The unique key identifier for the credential to retrieve. "
            "Examples: GMAIL_PASS, SAP_LOGIN, SCADA_API_KEY. "
            "The operator configures these in the Reactive Settings > Credentials page."
        ),
    )


async def _async_get_secret(key_identifier: str) -> str:
    """Retrieve a decrypted credential from the secure vault."""
    from backend.core.database import AsyncSessionLocal
    from backend.services.credential_service import CredentialService

    logger.info("[Credential Tool] Requested key: %s", key_identifier)

    async with AsyncSessionLocal() as session:
        service = CredentialService(session)
        value = await service.get_decrypted_value(key_identifier)

    if value is None:
        return (
            f"ERROR: No credential found for key '{key_identifier}'. "
            "Ask the user to configure this credential in Reactive Settings > Credentials."
        )

    logger.info("[Credential Tool] Successfully retrieved key: %s", key_identifier)
    return value


get_secret_credential = StructuredTool.from_function(
    coroutine=_async_get_secret,
    name="get_secret_credential",
    description=(
        "Retrieve a stored secret credential (password, API key, etc.) from the "
        "operator's secure vault. Use this when you encounter a login screen, "
        "need an API key, or require any sensitive information to continue a task. "
        "You must provide the exact 'key_identifier' (e.g. GMAIL_PASS, SAP_LOGIN)."
    ),
    args_schema=_GetSecretArgs,
)
