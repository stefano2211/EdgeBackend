"""CredentialManager — secure credential lifecycle with automatic OAuth2 refresh.

Responsibilities:
  1. Read encrypted credentials from DB
  2. Decrypt via CredentialVault
  3. Auto-refresh OAuth2 access tokens when expired
  4. Inject credentials into stdio process env or HTTP headers
"""

from __future__ import annotations

import logging

from backend.integrations.credential_audit import log_credential_event, CredentialAction
from datetime import datetime, timezone
from typing import Any

from backend.integrations.credential_vault import CredentialVault
from backend.integrations.interfaces import ICredentialVault
from backend.integrations.models import IntegrationCredential, IntegrationInstance
from backend.integrations.oauth_refresh import get_refresh_handler
from backend.integrations.repositories import IntegrationInstanceRepository

logger = logging.getLogger(__name__)


class CredentialManager:
    """Manages credential retrieval, refresh, and injection."""

    def __init__(
        self,
        instance_repo: IntegrationInstanceRepository,
        vault: ICredentialVault | None = None,
    ) -> None:
        self._repo = instance_repo
        self._vault = vault or CredentialVault()

    # ------------------------------------------------------------------
    # Retrieval (with auto-refresh)
    # ------------------------------------------------------------------

    async def get_credentials(self, instance: IntegrationInstance) -> dict[str, str]:
        """Return decrypted credentials for an instance, refreshing OAuth2 if needed."""
        creds: dict[str, str] = {}
        refresh_token = None
        client_id = None
        client_secret = None
        access_token_cred: IntegrationCredential | None = None
        needs_migration = False

        for cred in instance.credentials:
            plain = self._vault.decrypt(cred.encrypted_value)
            creds[cred.credential_key] = plain

            # If any credential was encrypted with a legacy format (v1/v2), flag it for migration
            if self._vault.needs_reencryption(cred.encrypted_value):
                needs_migration = True

            # Track OAuth2 pieces for potential refresh
            key_lower = cred.credential_key.lower()
            if key_lower in ("refresh_token", "oauth_refresh_token"):
                refresh_token = plain
            elif key_lower in ("client_id", "oauth_client_id"):
                client_id = plain
            elif key_lower in ("client_secret", "oauth_client_secret"):
                client_secret = plain
            elif key_lower in ("access_token", "token"):
                access_token_cred = cred

        # OAuth2 auto-refresh
        if refresh_token and client_id and client_secret and access_token_cred:
            if self._is_expired(access_token_cred):
                logger.info("OAuth2 access token expired for instance=%s — refreshing", instance.id)
                new_access = await self._perform_refresh(
                    instance, refresh_token, client_id, client_secret, access_token_cred
                )
                creds[access_token_cred.credential_key] = new_access
                # Refresh already updates the DB with new encrypt version, but let's make sure
                needs_migration = False

        # If any credentials need migration to version 3 (HKDF), re-encrypt and update DB
        if needs_migration:
            try:
                for cred in instance.credentials:
                    plain = creds[cred.credential_key]
                    if self._vault.needs_reencryption(cred.encrypted_value):
                        cred.encrypted_value = self._vault.encrypt(plain)
                await self._repo.update(instance)
                logger.info("Auto-migrated credentials for instance %s to version 3 (HKDF)", instance.id)
            except Exception as e:
                logger.warning("Failed to auto-migrate credentials for instance %s: %s", instance.id, e)

        # Audit: log credential access (fire-and-forget, values never logged)
        try:
            from sqlalchemy.ext.asyncio import AsyncSession
            session = self._repo._session  # Access the underlying session
            await log_credential_event(
                session,
                CredentialAction.ACCESSED,
                user_id=instance.user_id,
                instance_id=instance.id,
                credential_key=",".join(creds.keys()),
                details=f"Decrypted {len(creds)} credentials for catalog '{instance.catalog.slug}'",
            )
        except Exception:
            pass  # Audit must never break the main flow

        return creds

    def _is_expired(self, cred: IntegrationCredential) -> bool:
        """Check if an access token has expired (with 60s buffer)."""
        if not cred.expires_at:
            return False
        return cred.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None)

    async def _perform_refresh(
        self,
        instance: IntegrationInstance,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        access_token_cred: IntegrationCredential,
    ) -> str:
        """Refresh the access token and persist it."""
        # Determine provider from catalog slug or env var mapping
        provider = self._detect_provider(instance)
        handler = get_refresh_handler(provider)

        if not handler:
            logger.warning("No refresh handler for provider='%s' — using stale token", provider)
            return self._vault.decrypt(access_token_cred.encrypted_value)

        try:
            result = await handler(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
            )
            new_access_token = result["access_token"]
            expires_in = result.get("expires_in", 3600)

            # Encrypt and update DB
            access_token_cred.encrypted_value = self._vault.encrypt(new_access_token)
            from datetime import timedelta
            access_token_cred.expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
            ).replace(tzinfo=None)
            await self._repo.update(instance)  # This will commit the session

            logger.info("OAuth2 token refreshed for instance=%s", instance.id)
            try:
                await log_credential_event(
                    self._repo._session,
                    CredentialAction.REFRESHED,
                    user_id=instance.user_id,
                    instance_id=instance.id,
                    credential_key="access_token",
                    details=f"OAuth2 token refreshed, expires_in={expires_in}s",
                )
            except Exception:
                pass
            return new_access_token
        except Exception as exc:
            logger.exception("OAuth2 refresh failed for instance=%s: %s", instance.id, exc)
            try:
                await log_credential_event(
                    self._repo._session,
                    CredentialAction.REFRESH_FAILED,
                    user_id=instance.user_id,
                    instance_id=instance.id,
                    credential_key="access_token",
                    details=f"Refresh failed: {exc}",
                )
            except Exception:
                pass
            # Return existing (possibly expired) token — caller will likely fail,
            # but we don't want to crash the whole flow.
            return self._vault.decrypt(access_token_cred.encrypted_value)

    def _detect_provider(self, instance: IntegrationInstance) -> str:
        """Detect OAuth provider from catalog metadata."""
        if not instance.catalog:
            return "unknown"
        slug = instance.catalog.slug.lower()
        if "google" in slug or "gmail" in slug:
            return "google"
        if "microsoft" in slug or "azure" in slug or "outlook" in slug:
            return "microsoft"
        if "github" in slug:
            return "github"
        if "slack" in slug:
            return "slack"
        # Explicit error instead of silent fallback to Google
        logger.warning(
            "Unknown OAuth provider for catalog '%s' — no refresh handler available",
            instance.catalog.slug,
        )
        return "unknown"

    # ------------------------------------------------------------------
    # Injection helpers
    # ------------------------------------------------------------------

    def inject_for_stdio(
        self,
        credentials: dict[str, str],
        env_prefix: str | None,
        base_env: dict[str, str] | None = None,
        auth_env_var_mapping: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Merge credentials into a dict suitable for os.environ / Popen env.

        Uses auth_env_var_mapping to translate credential keys to env var names.
        Example:
            credentials = {"token": "ghp_xxx"}
            env_prefix = "GITHUB_"
            auth_env_var_mapping = {"PERSONAL_ACCESS_TOKEN": "token"}
            → env["GITHUB_PERSONAL_ACCESS_TOKEN"] = "ghp_xxx"
        """
        env = dict(base_env) if base_env else {}
        prefix = (env_prefix or "").upper()
        # Build reverse mapping: credential_key -> env_var_name
        reverse_mapping: dict[str, str] = {}
        if auth_env_var_mapping:
            for env_name, cred_key in auth_env_var_mapping.items():
                reverse_mapping[cred_key.lower()] = env_name.upper()

        for key, value in credentials.items():
            key_lower = key.lower()
            env_name = reverse_mapping.get(key_lower, key.upper())
            env_key = f"{prefix}{env_name}"
            env[env_key] = value
        return env

    def inject_for_http(
        self,
        credentials: dict[str, str],
        auth_type: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Add auth headers for REST bridge calls.

        Supports: api_key, bearer, basic, oauth2.
        """
        headers = dict(headers) if headers else {}

        if auth_type == "api_key":
            key = credentials.get("api_key") or credentials.get("token")
            if key:
                headers["X-Api-Key"] = key

        elif auth_type in ("token", "bearer", "oauth2"):
            token = (
                credentials.get("access_token")
                or credentials.get("token")
                or credentials.get("bearer")
            )
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "basic":
            import base64

            user = credentials.get("username") or credentials.get("user")
            pwd = credentials.get("password") or credentials.get("pass")
            if user and pwd:
                creds_b64 = base64.b64encode(f"{user}:{pwd}".encode()).decode()
                headers["Authorization"] = f"Basic {creds_b64}"

        return headers
