"""Local stdio MCP server for Gmail: send email, search, download attachments to Google Drive."""

__version__ = "0.1.0"

# Google OAuth scopes required by this server (least-privilege).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
]
