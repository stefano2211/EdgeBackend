"""Integrations router — exposes the full third-party MCP lifecycle.

Endpoints:
  /integrations/catalog          → browse available integrations
  /integrations/instances        → manage user instances
  /integrations/instances/{id}/setup-guide   → setup instructions
  /integrations/instances/{id}/credentials   → submit secrets + launch stdio process
  /integrations/instances/{id}/sync          → discover & register tools
  /integrations/instances/{id}/status        → runtime status
  /integrations/instances/{id}/stop          → stop stdio process
"""

from __future__ import annotations

from typing import Any

import html
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.deps import get_current_user, get_db
from backend.integrations.catalog_service import CatalogService
from backend.integrations.integration_service import IntegrationService
from backend.integrations.oauth.gmail_flow import build_authorization_url, generate_pkce_pair
from backend.integrations.oauth.state_manager import get_state_manager
from backend.integrations.schemas import (
    CredentialsSubmit,
    IntegrationCatalogOut,
    IntegrationInstanceCreate,
    IntegrationInstanceOut,
    IntegrationInstanceUpdate,
    IntegrationInstanceDetailOut,
    SetupGuideOut,
)
from backend.persistencia.models.user import User

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service(session: AsyncSession) -> IntegrationService:
    return IntegrationService(session)


def _catalog_service() -> CatalogService:
    return CatalogService()


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

@router.get("/catalog", response_model=list[IntegrationCatalogOut])
async def list_catalog(
    current_user: User = Depends(get_current_user),
):
    """List all enabled integrations available for setup."""
    service = _catalog_service()
    items = await service.list_catalog(enabled_only=True)
    return items


@router.get("/catalog/{slug}", response_model=IntegrationCatalogOut)
async def get_catalog_item(
    slug: str,
    current_user: User = Depends(get_current_user),
):
    """Get details of a single catalog entry."""
    service = _catalog_service()
    catalog = await service.get_by_slug(slug)
    if not catalog:
        raise HTTPException(status_code=404, detail=f"Catalog '{slug}' not found")
    return catalog


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

@router.post("/instances", response_model=IntegrationInstanceOut, status_code=201)
async def create_instance(
    data: IntegrationInstanceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Create a new integration instance (stdio process NOT started yet)."""
    service = _service(session)
    try:
        instance = await service.create_instance(current_user.id, data)
        return instance
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/instances", response_model=list[IntegrationInstanceOut])
async def list_instances(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all integration instances owned by the current user."""
    service = _service(session)
    return await service.list_instances(current_user.id)


@router.get("/instances/{instance_id}", response_model=IntegrationInstanceDetailOut)
async def get_instance(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get detailed view of a single instance including nested catalog."""
    service = _service(session)
    try:
        instance = await service.get_instance(instance_id, current_user.id)
        return instance
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/instances/{instance_id}", response_model=IntegrationInstanceOut)
async def update_instance(
    instance_id: int,
    data: IntegrationInstanceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Update instance metadata (name, availability flags)."""
    service = _service(session)
    try:
        return await service.update_instance(instance_id, current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/instances/{instance_id}", status_code=204)
async def delete_instance(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete instance, process, credentials, and registered tools permanently."""
    service = _service(session)
    try:
        await service.delete_instance(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return None


# ---------------------------------------------------------------------------
# Setup guide
# ---------------------------------------------------------------------------

@router.get("/instances/{instance_id}/setup-guide", response_model=SetupGuideOut)
async def get_setup_guide(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Return setup instructions and required credential fields."""
    service = _service(session)
    try:
        guide = await service.get_setup_guide(instance_id, current_user.id)
        return SetupGuideOut(**guide)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

@router.post("/instances/{instance_id}/credentials", response_model=IntegrationInstanceOut)
async def submit_credentials(
    instance_id: int,
    data: CredentialsSubmit,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Submit raw credentials, encrypt them, and launch the MCP stdio process."""
    service = _service(session)
    try:
        return await service.submit_credentials(instance_id, current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---------------------------------------------------------------------------
# OAuth flows
# ---------------------------------------------------------------------------

class OAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


@router.post("/instances/{instance_id}/oauth/{provider}/start", response_model=OAuthStartResponse)
async def oauth_start(
    instance_id: int,
    provider: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Start a managed OAuth2 flow for the given instance.

    The backend uses its own Google Cloud credentials (GMAIL_CLIENT_ID /
    GMAIL_CLIENT_SECRET from settings). The frontend only needs to open the
    returned authorization_url in a popup.
    """
    if provider != "gmail":
        raise HTTPException(status_code=400, detail=f"Unsupported OAuth provider: {provider}")

    if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="Gmail OAuth is not configured on the server. Please contact the administrator.",
        )

    service = _service(session)
    try:
        instance = await service.get_instance(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    catalog = instance.catalog
    if not catalog or catalog.auth_type != "oauth2":
        raise HTTPException(status_code=400, detail="This integration does not use OAuth2 or catalog config is missing")

    # Resolve frontend origin dynamically from request headers
    frontend_origin = request.headers.get("origin")
    if not frontend_origin:
        referer = request.headers.get("referer")
        if referer:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            frontend_origin = f"{parsed.scheme}://{parsed.netloc}"
    if not frontend_origin:
        frontend_origin = settings.FRONTEND_ORIGIN

    code_verifier, code_challenge = generate_pkce_pair()
    state_manager = get_state_manager()
    state = await state_manager.create(
        instance_id=instance_id,
        user_id=current_user.id,
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
        code_verifier=code_verifier,
        provider=provider,
        frontend_origin=frontend_origin,
    )

    auth_url = build_authorization_url(
        client_id=settings.GMAIL_CLIENT_ID,
        redirect_uri=settings.OAUTH_REDIRECT_URL,
        state=state,
        code_challenge=code_challenge,
    )

    return OAuthStartResponse(authorization_url=auth_url, state=state)


@router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """OAuth2 callback from Google (public endpoint).

    Exchanges the authorization code for tokens, stores them, launches the
    stdio process, and returns an HTML page that posts a message back to the
    opener window and closes the popup.
    """
    template_path = Path(__file__).parent / "oauth" / "callback_template.html"
    template = template_path.read_text(encoding="utf-8")

    # Resolve target origin from stored OAuth state if possible
    frontend_origin = settings.FRONTEND_ORIGIN
    if state:
        state_manager = get_state_manager()
        ctx = await state_manager.peek(state)
        if ctx and "frontend_origin" in ctx and ctx["frontend_origin"]:
            frontend_origin = ctx["frontend_origin"]

    if error:
        escaped_error = html.escape(error)
        payload = {"type": "oauth-error", "provider": "gmail", "error": error, "error_description": error_description}
        html_content = (
            template
            .replace("{{icon}}", "❌")
            .replace("{{title}}", "Authorization failed")
            .replace("{{message}}", f"{escaped_error}. This window will close automatically.")
            .replace("{{payload_json}}", json.dumps(payload).replace("</", "<\\/"))
            .replace("{{origin}}", html.escape(frontend_origin))
        )
        return HTMLResponse(content=html_content, status_code=400)

    if not code or not state:
        payload = {"type": "oauth-error", "provider": "gmail", "error": "missing_params"}
        html_content = (
            template
            .replace("{{icon}}", "❌")
            .replace("{{title}}", "Invalid request")
            .replace("{{message}}", "Missing code or state. This window will close automatically.")
            .replace("{{payload_json}}", json.dumps(payload).replace("</", "<\\/"))
            .replace("{{origin}}", html.escape(frontend_origin))
        )
        return HTMLResponse(content=html_content, status_code=400)

    from backend.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        service = IntegrationService(session)
        try:
            await service.complete_oauth(
                code=code,
                state=state,
            )
            payload = {"type": "oauth-success", "provider": "gmail"}
            html_content = (
                template
                .replace("{{icon}}", "✅")
                .replace("{{title}}", "Authorization successful")
                .replace("{{message}}", "Gmail connected successfully. This window will close automatically.")
                .replace("{{payload_json}}", json.dumps(payload).replace("</", "<\\/"))
                .replace("{{origin}}", html.escape(frontend_origin))
            )
            return HTMLResponse(content=html_content)
        except ValueError as exc:
            escaped_exc = html.escape(str(exc))
            payload = {"type": "oauth-error", "provider": "gmail", "error": "validation", "detail": str(exc)}
            html_content = (
                template
                .replace("{{icon}}", "❌")
                .replace("{{title}}", "Authorization failed")
                .replace("{{message}}", f"{escaped_exc}. This window will close automatically.")
                .replace("{{payload_json}}", json.dumps(payload).replace("</", "<\\/"))
                .replace("{{origin}}", html.escape(frontend_origin))
            )
            return HTMLResponse(content=html_content, status_code=400)
        except RuntimeError as exc:
            escaped_exc = html.escape(str(exc))
            payload = {"type": "oauth-error", "provider": "gmail", "error": "runtime", "detail": str(exc)}
            html_content = (
                template
                .replace("{{icon}}", "❌")
                .replace("{{title}}", "Authorization failed")
                .replace("{{message}}", f"{escaped_exc}. This window will close automatically.")
                .replace("{{payload_json}}", json.dumps(payload).replace("</", "<\\/"))
                .replace("{{origin}}", html.escape(frontend_origin))
            )
            return HTMLResponse(content=html_content, status_code=502)


# ---------------------------------------------------------------------------
# Sync / Re-discovery
# ---------------------------------------------------------------------------

@router.post("/instances/{instance_id}/sync", response_model=IntegrationInstanceOut)
async def sync_instance(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Force re-discovery and re-registration of tools for an instance.

    Call this after toggling 'available_in_chat' or 'available_in_reactive'
    on an existing instance, or when the MCP server tools have changed.
    """
    service = _service(session)
    try:
        return await service.sync_instance(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---------------------------------------------------------------------------
# Process lifecycle
# ---------------------------------------------------------------------------

@router.post("/instances/{instance_id}/stop", response_model=IntegrationInstanceOut)
async def stop_instance_process(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Stop the stdio process (preserves data in DB)."""
    service = _service(session)
    try:
        return await service.stop_process(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/instances/{instance_id}/status")
async def get_instance_status(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get stdio process runtime status."""
    service = _service(session)
    try:
        return await service.get_status(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
