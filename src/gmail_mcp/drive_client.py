"""Google Drive operations: resolve-or-create a folder and upload bytes into it.

With the drive.file scope the server only sees/manages files it created, so the destination folder
is one this server owns (default "Gmail Attachments").
"""

import io

from googleapiclient.http import MediaIoBaseUpload

FOLDER_MIME = "application/vnd.google-apps.folder"


def _escape_query_value(value):
    """Escape backslashes and single quotes for a Drive query string literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def find_or_create_folder(service, name):
    """Return the id of the named folder (among app-created files), creating it if absent."""
    q = (
        f"mimeType='{FOLDER_MIME}' and name='{_escape_query_value(name)}' "
        "and trashed=false"
    )
    resp = service.files().list(q=q, spaces="drive", fields="files(id,name)").execute()
    files = resp.get("files", []) or []
    if files:
        return files[0]["id"]
    created = (
        service.files()
        .create(body={"name": name, "mimeType": FOLDER_MIME}, fields="id")
        .execute()
    )
    return created["id"]


def upload_bytes(service, data, filename, mime_type, folder_id):
    """Upload raw bytes as a file into the given folder; return id/name/web link."""
    media = MediaIoBaseUpload(
        io.BytesIO(data), mimetype=mime_type or "application/octet-stream", resumable=False
    )
    created = (
        service.files()
        .create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id,name,webViewLink",
        )
        .execute()
    )
    return {
        "file_id": created.get("id"),
        "name": created.get("name"),
        "web_view_link": created.get("webViewLink"),
    }
