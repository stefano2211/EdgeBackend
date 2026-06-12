"""Static catalogue of available third-party integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class IntegrationCatalogConfig:
    slug: str
    name: str
    description: str | None = None
    icon_url: str | None = None
    category: str | None = None
    source_type: str = "official"  # "official" | "custom" | "rest_bridge"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env_prefix: str | None = None
    rest_bridge_url_template: str | None = None
    auth_type: str = "none"  # "token" | "oauth2" | "basic" | "connection_string" | "api_key" | "none"
    auth_env_var_mapping: dict[str, str] = field(default_factory=dict)
    auth_setup_guide_markdown: str | None = None
    is_enabled: bool = True
    is_official_verified: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Added mock ID to maintain backwards compatibility with Pydantic serialization
    @property
    def id(self) -> int:
        # Generate a stable positive integer hash of the slug using SHA-256
        # (Python's built-in hash() is salted per-process and changes between restarts)
        import hashlib
        return int(hashlib.sha256(self.slug.encode("utf-8")).hexdigest()[:8], 16)


CATALOG: dict[str, IntegrationCatalogConfig] = {
    "github": IntegrationCatalogConfig(
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
        is_official_verified=True,
        auth_setup_guide_markdown="""## GitHub Setup

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Select scopes: at minimum `repo` for private repositories
4. Copy the generated token (starts with `ghp_`)
5. Paste it below in the **token** field.
""",
    ),
    "slack": IntegrationCatalogConfig(
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
        is_official_verified=True,
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
    "postgres": IntegrationCatalogConfig(
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
        is_official_verified=True,
        auth_setup_guide_markdown="""## PostgreSQL Setup

Provide a connection string in the format:
```
postgresql://user:password@host:port/database
```
Paste it below in the **connection_string** field.
""",
    ),
    "gmail": IntegrationCatalogConfig(
        slug="gmail",
        name="Gmail",
        description="Send and read emails via a custom Gmail MCP server with OAuth2 support.",
        category="communication",
        source_type="custom",
        command="python",
        args=["-m", "backend.integrations.custom_mcp_servers.gmail.server"],
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
    "aws": IntegrationCatalogConfig(
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
        is_official_verified=True,
        auth_setup_guide_markdown="""## AWS Setup

1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Create a new user with programmatic access
3. Attach policies: `AmazonS3ReadOnlyAccess`, `CloudWatchReadOnlyAccess`
4. Copy **Access key ID** and **Secret access key**
5. Paste both below along with your preferred AWS region (e.g. `us-east-1`).
""",
    ),
    "notion": IntegrationCatalogConfig(
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
        is_official_verified=True,
        auth_setup_guide_markdown="""## Notion Setup

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the **Internal Integration Token** (starts with `secret_`)
4. Share your Notion pages with the integration
5. Paste the token below in the **api_key** field.
""",
    ),
}
