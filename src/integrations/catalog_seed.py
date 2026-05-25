"""Auto-seed data for the integration catalog.

This module contains the canonical list of pre-configured third-party
integrations.  It is imported by:
  - src.main      → startup auto-seed (if table is empty)
  - seed_catalog  → manual CLI seed script
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.catalog_service import CatalogService
from src.integrations.schemas import IntegrationCatalogCreate

logger = logging.getLogger(__name__)

CATALOG_SEED = [
    IntegrationCatalogCreate(
        slug="github",
        name="GitHub",
        description="Access repositories, issues, pull requests and commits via the official GitHub MCP server.",
        category="development",
        source_type="official",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env_prefix="GITHUB_",
        auth_type="token",
        auth_env_var_mapping={"PERSONAL_ACCESS_TOKEN": "token"},
        auth_setup_guide_markdown="""## GitHub Setup

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Select scopes: at minimum `repo` for private repositories
4. Copy the generated token (starts with `ghp_`)
5. Paste it below in the **token** field.
""",
    ),
    IntegrationCatalogCreate(
        slug="slack",
        name="Slack",
        description="Send messages and read channel history via the official Slack MCP server.",
        category="communication",
        source_type="official",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-slack"],
        env_prefix="SLACK_",
        auth_type="token",
        auth_env_var_mapping={"BOT_TOKEN": "token", "TEAM_ID": "team_id"},
        auth_setup_guide_markdown="""## Slack Setup

1. Go to [Slack API → Your Apps](https://api.slack.com/apps)
2. Create a new app (from scratch)
3. Go to **OAuth & Permissions**
4. Add scopes: `chat:write`, `channels:read`, `channels:history`
5. Install to workspace and copy **Bot User OAuth Token** (starts with `xoxb-`)
6. Find your **Team ID** in Slack settings → Workspace settings
7. Paste both values below.
""",
    ),
    IntegrationCatalogCreate(
        slug="postgres",
        name="PostgreSQL",
        description="Query PostgreSQL databases via the official MCP server.",
        category="database",
        source_type="official",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres"],
        env_prefix="POSTGRES_",
        auth_type="connection_string",
        auth_env_var_mapping={"CONNECTION_STRING": "connection_string"},
        auth_setup_guide_markdown="""## PostgreSQL Setup

Provide a connection string in the format:
```
postgresql://user:password@host:port/database
```
Paste it below in the **connection_string** field.
""",
    ),
    IntegrationCatalogCreate(
        slug="gmail",
        name="Gmail",
        description="Send and read emails via a custom Gmail MCP server with OAuth2 support.",
        category="communication",
        source_type="custom",
        command="python",
        args=["-m", "src.integrations.custom_mcp_servers.gmail.server"],
        env_prefix="GMAIL_",
        auth_type="oauth2",
        auth_env_var_mapping={
            "REFRESH_TOKEN": "refresh_token",
            "CLIENT_ID": "client_id",
            "CLIENT_SECRET": "client_secret",
        },
        auth_setup_guide_markdown="""## Gmail Setup — Step by Step

### Step 1: Create a Google Cloud project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)

### Step 2: Enable the Gmail API
1. Navigate to **APIs & Services** → **Library**
2. Search for **Gmail API** and click **Enable**

### Step 3: Configure OAuth consent screen
1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** → click **Create**
3. Fill in:
   - **App name**: anything (e.g. "EdgeBackend Gmail")
   - **User support email**: your email
   - **Developer contact email**: your email
4. Click **Save and Continue**
5. On the **Scopes** step, click **Add or Remove Scopes**
6. Search for `https://www.googleapis.com/auth/gmail.modify` and check it
7. Click **Update**, then **Save and Continue**
8. On **Test users**, click **Add Users** and add your Gmail address
9. Click **Save and Continue**, then **Back to Dashboard**

### Step 4: Create OAuth credentials
1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Select **Desktop app** as application type
4. Name it (e.g. "EdgeBackend Desktop")
5. Click **Create**
6. Click **DOWNLOAD JSON** — save this file as `client_secret.json`

### Step 5: Get your Refresh Token (run this script)
```bash
# Install the helper
pip install google-auth-oauthlib

# Download the script from our repo:
# src/integrations/custom_mcp_servers/gmail/get_gmail_refresh_token.py

# Run it
python get_gmail_refresh_token.py
```

The script will:
- Open a browser window
- Ask you to log in with your Gmail account
- Print the 3 values you need below

### Step 6: Paste the values into the form below

| Field | What it is |
|-------|-----------|
| **refresh_token** | The long token printed by the script (starts with `1//...`) |
| **client_id** | Your OAuth Client ID (ends with `...apps.googleusercontent.com`) |
| **client_secret** | Your OAuth Client Secret (a 24-character random string) |
""",
    ),
    IntegrationCatalogCreate(
        slug="aws",
        name="AWS",
        description="Interact with AWS services (S3, CloudWatch, EC2) via the official AWS MCP server.",
        category="cloud",
        source_type="official",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-aws"],
        env_prefix="AWS_",
        auth_type="token",
        auth_env_var_mapping={
            "ACCESS_KEY_ID": "access_key_id",
            "SECRET_ACCESS_KEY": "secret_access_key",
            "REGION": "region",
        },
        auth_setup_guide_markdown="""## AWS Setup

1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Create a new user with programmatic access
3. Attach policies: `AmazonS3ReadOnlyAccess`, `CloudWatchReadOnlyAccess`
4. Copy **Access key ID** and **Secret access key**
5. Paste both below along with your preferred AWS region (e.g. `us-east-1`).
""",
    ),
    IntegrationCatalogCreate(
        slug="notion",
        name="Notion",
        description="Read and write Notion pages via the official Notion MCP server.",
        category="productivity",
        source_type="official",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-notion"],
        env_prefix="NOTION_",
        auth_type="api_key",
        auth_env_var_mapping={"API_TOKEN": "api_key"},
        auth_setup_guide_markdown="""## Notion Setup

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the **Internal Integration Token** (starts with `secret_`)
4. Share your Notion pages with the integration
5. Paste the token below in the **api_key** field.
""",
    ),
    IntegrationCatalogCreate(
        slug="maquinaria",
        name="Monitoreo Maquinaria",
        description="Consulta métricas industriales en tiempo real (temperatura, vibración, presión, corriente, RPM) desde el servidor de pruebas apiEjemplo.",
        category="industrial",
        source_type="custom",
        command="python",
        args=["-m", "src.integrations.custom_mcp_servers.maquinaria.server"],
        env_prefix="MAQUINARIA_",
        auth_type="none",
        auth_env_var_mapping={},
        auth_setup_guide_markdown="""## Setup Monitoreo Maquinaria

1. Asegúrate de que **apiEjemplo** esté corriendo en `http://localhost:7000`
   (o en la URL configurada en la variable de entorno `MAQUINARIA_API_URL`).
2. Esta integración no requiere credenciales — se conecta directamente vía HTTP REST.
3. Una vez creada la instancia, el proceso stdio arrancará automáticamente
   y descubrirá las tools disponibles (`get_machinery_metrics`, `list_equipment_status`).
""",
    ),
]


async def seed_integration_catalog(session: AsyncSession) -> tuple[int, int]:
    """Idempotently seed the catalog.  Returns (created_count, skipped_count)."""
    from sqlalchemy.exc import IntegrityError

    service = CatalogService(session)
    created = 0
    skipped = 0

    for entry in CATALOG_SEED:
        existing = await service.get_by_slug(entry.slug)
        if existing:
            logger.debug("Catalog seed: '%s' already exists — skipping", entry.slug)
            skipped += 1
            continue

        try:
            await service.create(entry)
            logger.info("Catalog seed: created entry '%s'", entry.slug)
            created += 1
        except IntegrityError:
            logger.debug("Catalog seed: '%s' already exists (race) — skipping", entry.slug)
            skipped += 1
            await session.rollback()

    if created:
        logger.info("Catalog auto-seed complete: %d created, %d skipped", created, skipped)
    return created, skipped
