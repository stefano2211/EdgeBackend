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
        official_package="@modelcontextprotocol/server-github",
        official_command="npx",
        official_args=["-y", "@modelcontextprotocol/server-github"],
        auth_type="token",
        auth_env_var_mapping={"GITHUB_PERSONAL_ACCESS_TOKEN": "token"},
        auth_setup_guide_markdown="""## GitHub Setup

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Select scopes: at minimum `repo` for private repositories
4. Copy the generated token (starts with `ghp_`)
5. Paste it below in the **token** field.
""",
        requires_docker=True,
    ),
    IntegrationCatalogCreate(
        slug="slack",
        name="Slack",
        description="Send messages and read channel history via the official Slack MCP server.",
        category="communication",
        source_type="official",
        official_package="@modelcontextprotocol/server-slack",
        official_command="npx",
        official_args=["-y", "@modelcontextprotocol/server-slack"],
        auth_type="token",
        auth_env_var_mapping={"SLACK_BOT_TOKEN": "token", "SLACK_TEAM_ID": "team_id"},
        auth_setup_guide_markdown="""## Slack Setup

1. Go to [Slack API → Your Apps](https://api.slack.com/apps)
2. Create a new app (from scratch)
3. Go to **OAuth & Permissions**
4. Add scopes: `chat:write`, `channels:read`, `channels:history`
5. Install to workspace and copy **Bot User OAuth Token** (starts with `xoxb-`)
6. Find your **Team ID** in Slack settings → Workspace settings
7. Paste both values below.
""",
        requires_docker=True,
    ),
    IntegrationCatalogCreate(
        slug="postgres",
        name="PostgreSQL",
        description="Query PostgreSQL databases via the official MCP server.",
        category="database",
        source_type="official",
        official_package="@modelcontextprotocol/server-postgres",
        official_command="npx",
        official_args=["-y", "@modelcontextprotocol/server-postgres"],
        auth_type="basic",
        auth_env_var_mapping={"POSTGRES_CONNECTION_STRING": "connection_string"},
        auth_setup_guide_markdown="""## PostgreSQL Setup

Provide a connection string in the format:
```
postgresql://user:password@host:port/database
```
Paste it below in the **connection_string** field.
""",
        requires_docker=True,
    ),
    IntegrationCatalogCreate(
        slug="gmail",
        name="Gmail",
        description="Send and read emails via a custom Gmail MCP server with OAuth2 support.",
        category="communication",
        source_type="custom",
        custom_module_path="src.integrations.custom_mcp_servers.gmail.server",
        docker_image="edgebackend/gmail-mcp-server",
        auth_type="oauth2",
        auth_env_var_mapping={
            "GMAIL_REFRESH_TOKEN": "refresh_token",
            "GMAIL_CLIENT_ID": "client_id",
            "GMAIL_CLIENT_SECRET": "client_secret",
        },
        auth_setup_guide_markdown="""## Gmail Setup (Manual OAuth2)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Gmail API** in APIs & Services → Library
4. Go to **Credentials** → Create credentials → OAuth client ID
5. Configure consent screen (External) and add scope: `https://www.googleapis.com/auth/gmail.send`
6. Download the client credentials JSON
7. Use a tool or script to exchange authorization code for a **refresh token**:
   ```python
   from google_auth_oauthlib.flow import InstalledAppFlow
   flow = InstalledAppFlow.from_client_secrets_file(
       'client_secret.json',
       scopes=['https://www.googleapis.com/auth/gmail.send']
   )
   creds = flow.run_local_server(port=0)
   print('Refresh token:', creds.refresh_token)
   ```
8. Copy the **refresh_token**, **client_id**, and **client_secret** below.
""",
        requires_docker=True,
    ),
    IntegrationCatalogCreate(
        slug="aws",
        name="AWS",
        description="Interact with AWS services (S3, CloudWatch, EC2) via the official AWS MCP server.",
        category="cloud",
        source_type="official",
        official_package="@modelcontextprotocol/server-aws",
        official_command="npx",
        official_args=["-y", "@modelcontextprotocol/server-aws"],
        auth_type="token",
        auth_env_var_mapping={
            "AWS_ACCESS_KEY_ID": "access_key_id",
            "AWS_SECRET_ACCESS_KEY": "secret_access_key",
            "AWS_REGION": "region",
        },
        auth_setup_guide_markdown="""## AWS Setup

1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Create a new user with programmatic access
3. Attach policies: `AmazonS3ReadOnlyAccess`, `CloudWatchReadOnlyAccess`
4. Copy **Access key ID** and **Secret access key**
5. Paste both below along with your preferred AWS region (e.g. `us-east-1`).
""",
        requires_docker=True,
    ),
    IntegrationCatalogCreate(
        slug="notion",
        name="Notion",
        description="Read and write Notion pages via the official Notion MCP server.",
        category="productivity",
        source_type="official",
        official_package="@modelcontextprotocol/server-notion",
        official_command="npx",
        official_args=["-y", "@modelcontextprotocol/server-notion"],
        auth_type="api_key",
        auth_env_var_mapping={"NOTION_API_TOKEN": "api_key"},
        auth_setup_guide_markdown="""## Notion Setup

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the **Internal Integration Token** (starts with `secret_`)
4. Share your Notion pages with the integration
5. Paste the token below in the **api_key** field.
""",
        requires_docker=True,
    ),
]


async def seed_integration_catalog(session: AsyncSession) -> tuple[int, int]:
    """Idempotently seed the catalog.  Returns (created_count, skipped_count)."""
    service = CatalogService(session)
    created = 0
    skipped = 0

    for entry in CATALOG_SEED:
        existing = await service.get_by_slug(entry.slug)
        if existing:
            logger.debug("Catalog seed: '%s' already exists — skipping", entry.slug)
            skipped += 1
            continue

        await service.create(entry)
        logger.info("Catalog seed: created entry '%s'", entry.slug)
        created += 1

    if created:
        logger.info("Catalog auto-seed complete: %d created, %d skipped", created, skipped)
    return created, skipped
