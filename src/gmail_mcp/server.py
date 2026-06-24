"""FastMCP stdio server exposing three Gmail tools to a local Claude client.

Credentials are loaded from AWS SSM at call time (see auth.py). Run with `gmail-mcp` or
`python -m gmail_mcp.server`.
"""

import logging

from mcp.server.fastmcp import FastMCP

from . import attachments, auth, gmail_client
from .attachments import DEFAULT_FOLDER

logging.basicConfig(level=logging.INFO)

mcp = FastMCP("gmail-mcp")


@mcp.tool()
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    html: bool = False,
) -> dict:
    """Send an email from the configured Gmail account.

    `to`, `cc`, `bcc` accept a single address or a comma-separated list. Set `html=true` to send
    `body` as HTML. Returns the Gmail message id and thread id.
    """
    gmail, _ = auth.get_services()
    return gmail_client.send_email(
        gmail,
        to=to,
        subject=subject,
        body=body,
        cc=cc or None,
        bcc=bcc or None,
        html=html,
    )


@mcp.tool()
def search_emails(query: str, max_results: int = 10) -> list:
    """Search Gmail using a standard Gmail query (e.g. 'has:attachment from:bob newer_than:7d').

    Returns a list of message summaries: id, from, to, subject, date, snippet, and any attachment
    metadata (attachment_id, filename, mime_type, size) needed by download_attachment.
    """
    gmail, _ = auth.get_services()
    return gmail_client.search_emails(gmail, query, max_results=max_results)


@mcp.tool()
def download_attachment(
    message_id: str,
    attachment_id: str = "",
    filename: str = "",
    drive_folder: str = DEFAULT_FOLDER,
) -> dict:
    """Download an attachment from a Gmail message and upload it to Google Drive.

    Identify the attachment by `filename` (preferred — stable across requests) or `attachment_id`;
    if the message has exactly one attachment, neither is required. Uploads into the Drive folder
    `drive_folder` (created if absent). Returns the Drive file id, name, and web_view_link.
    """
    gmail, drive = auth.get_services()
    return attachments.download_attachment_to_drive(
        gmail,
        drive,
        message_id,
        attachment_id=attachment_id or None,
        filename=filename or None,
        folder_name=drive_folder or DEFAULT_FOLDER,
    )


@mcp.tool()
def download_attachment_local(
    message_id: str,
    dest_dir: str,
    attachment_id: str = "",
    filename: str = "",
) -> dict:
    """Download an attachment from a Gmail message and save it to a local directory.

    Identify the attachment by `filename` (preferred — stable across requests) or `attachment_id`;
    if the message has exactly one attachment, neither is required. `dest_dir` is expanded (`~`)
    and created if absent. Returns the absolute `path`, `name`, and `size_bytes` of the saved file.
    """
    gmail, _ = auth.get_services()
    return attachments.download_attachment_to_local(
        gmail,
        message_id,
        dest_dir,
        attachment_id=attachment_id or None,
        filename=filename or None,
    )


def main():
    """Entry point: run the server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
