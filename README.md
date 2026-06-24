# gmail-mcp

A local **stdio** [MCP](https://modelcontextprotocol.io) server that gives your local Claude clients
three Gmail tools:

| Tool | What it does |
|------|--------------|
| `send_email` | Send mail from your Gmail/Workspace address (plain or HTML, cc/bcc). Every send is logged. |
| `search_emails` | Search Gmail (`has:attachment from:bob newer_than:7d`…) and return message summaries **including attachment metadata**. |
| `download_attachment` | Pull an attachment from a message and **upload it to your Google Drive**, returning the Drive link. |

## Design

- **Local stdio** — no public endpoint, no OAuth-for-callers, no server to host. Runs as a subprocess
  of your Claude client.
- **Single Google account** for both Gmail and Drive.
- **Least-privilege scopes** — `gmail.send`, `gmail.readonly`, `drive.file` (the app only ever sees
  Drive files it created).
- **Credentials in AWS SSM** — the refresh token lives in an SSM SecureString and is fetched at
  launch; nothing is written to disk. **Requires AWS credentials at runtime** (e.g. an `AWS_PROFILE`).
- Attachments upload into a Drive folder named **`Gmail Attachments`** by default (created on first
  use; override per call with the `drive_folder` argument).

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (manages Python 3.12 + deps).
- AWS credentials with read/write access to the SSM parameter (any standard method — `AWS_PROFILE`,
  env vars, instance role). A region from your AWS config, env `AWS_REGION`, or `GMAIL_MCP_AWS_REGION`.
- A **Google Cloud project** with the **Gmail API** and **Google Drive API** enabled
  (Console → APIs & Services → Library).
- A Google **OAuth client of type "Desktop app"** — download its `client_secret.json`
  (Console → APIs & Services → Credentials).

## One-time setup: mint the token

Runs a browser consent for the three scopes and stores the credentials in SSM
(default param `/gmail-mcp/authorized-user-json`).

```bash
cd /path/to/gmail-mcp

# Using a downloaded Desktop client_secret.json:
AWS_PROFILE=<your-aws-profile> \
  uv run python scripts/mint_token.py --client-secrets-file /path/to/client_secret.json

# ...or reuse an existing Google token already in SSM (its client_id/secret):
AWS_PROFILE=<your-aws-profile> \
  uv run python scripts/mint_token.py --client-secrets-ssm-param /path/to/existing-token
```

A browser window opens — approve access for the intended account. On success the token is written to
SSM and the server can run.

## Register with your Claude client(s)

Replace `/path/to/gmail-mcp` and `<your-aws-profile>` with your values.

### Claude Code

```bash
claude mcp add gmail-mcp -s user \
  -e AWS_PROFILE=<your-aws-profile> \
  -- uv run --directory /path/to/gmail-mcp gmail-mcp
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "gmail-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/gmail-mcp", "gmail-mcp"],
      "env": { "AWS_PROFILE": "<your-aws-profile>" }
    }
  }
}
```

Restart Claude Desktop after editing. The three tools appear under the `gmail-mcp` server.

## Usage examples (things to ask Claude)

- "Email alice@example.com with the subject 'Lunch?' and body 'Free tomorrow at 1?'"
- "Search my Gmail for emails with attachments from the last week."
- "Download the PDF attached to that invoice email into my Drive."

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `AWS_PROFILE` (or any AWS cred) | — | AWS credentials used to read the token from SSM |
| `GMAIL_MCP_AWS_REGION` | standard AWS config | Region of the SSM parameter |
| `GMAIL_MCP_SSM_PARAM` | `/gmail-mcp/authorized-user-json` | SSM param holding the credentials JSON |
| `drive_folder` (tool arg) | `Gmail Attachments` | Destination Drive folder for downloads |

## Security

- The server can send mail as you. Every send is logged (recipients, subject, timestamp). There is no
  recipient allowlist by default; treat the tool as injection-sensitive.
- The refresh token never touches disk — only an SSM SecureString, fetched in-memory at launch.
- Scopes are least-privilege: read Gmail, send Gmail, and Drive access limited to app-created files.

## Development

```bash
uv sync
uv run pytest        # unit tests (all mocked; no live Google/AWS calls)
uv run ruff check .  # lint
```

Layout: `src/gmail_mcp/` — `auth.py` (SSM→credentials), `gmail_client.py` (send/search/attachments),
`drive_client.py` (folder + upload), `attachments.py` (orchestration), `server.py` (FastMCP wiring),
`bootstrap.py` (token mint).
