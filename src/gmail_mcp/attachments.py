"""Orchestration: pull an attachment from Gmail and store it (Drive or local disk)."""

import logging
import os

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


def download_attachment_to_local(
    gmail,
    message_id,
    dest_dir,
    attachment_id=None,
    filename=None,
):
    """Resolve an attachment, fetch its bytes, and write it to a local directory.

    `dest_dir` is expanded (``~``) and created if absent. The attachment's own filename is
    reduced to its basename to prevent path traversal. Returns {path, name, size_bytes}.
    """
    meta = gmail_client.resolve_attachment(gmail, message_id, attachment_id, filename)
    data = gmail_client.get_attachment_bytes(gmail, message_id, meta["attachment_id"])

    name = os.path.basename(meta["filename"])
    dest_dir = os.path.expanduser(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, name)
    with open(path, "wb") as fh:
        fh.write(data)

    logger.info(
        "downloaded attachment %r (%d bytes) from message %s to %s",
        name,
        len(data),
        message_id,
        path,
    )
    return {"path": path, "name": name, "size_bytes": len(data)}
