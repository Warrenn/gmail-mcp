"""Orchestration: pull an attachment from Gmail and upload it to Google Drive."""

import logging

from . import drive_client, gmail_client

logger = logging.getLogger("gmail_mcp.download")

DEFAULT_FOLDER = "Gmail Attachments"


def download_attachment_to_drive(
    gmail,
    drive,
    message_id,
    attachment_id=None,
    filename=None,
    folder_name=DEFAULT_FOLDER,
):
    """Resolve an attachment, fetch its bytes, and upload it to a Drive folder.

    Returns {file_id, name, web_view_link, drive_folder}.
    """
    meta = gmail_client.resolve_attachment(gmail, message_id, attachment_id, filename)
    data = gmail_client.get_attachment_bytes(gmail, message_id, meta["attachment_id"])
    folder_id = drive_client.find_or_create_folder(drive, folder_name)
    result = drive_client.upload_bytes(
        drive, data, meta["filename"], meta.get("mime_type", ""), folder_id
    )
    result["drive_folder"] = folder_name
    logger.info(
        "downloaded attachment %r (%d bytes) from message %s to Drive folder %r (file %s)",
        meta["filename"],
        len(data),
        message_id,
        folder_name,
        result.get("file_id"),
    )
    return result
