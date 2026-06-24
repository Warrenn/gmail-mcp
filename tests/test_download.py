"""Phase 4: download_attachment — fetch bytes from Gmail, upload to Google Drive."""

import base64

import pytest

import gmail_mcp.attachments as attachments
import gmail_mcp.drive_client as dc
import gmail_mcp.gmail_client as gc
from conftest import FakeDrive, FakeGmail

MSG = {
    "id": "m1",
    "threadId": "t1",
    "snippet": "file",
    "payload": {
        "mimeType": "multipart/mixed",
        "headers": [{"name": "Subject", "value": "Invoice"}],
        "parts": [
            {"mimeType": "text/plain", "body": {"size": 3}},
            {
                "mimeType": "application/pdf",
                "filename": "invoice.pdf",
                "body": {"size": 7, "attachmentId": "att-1"},
            },
            {
                "mimeType": "image/png",
                "filename": "logo.png",
                "body": {"size": 9, "attachmentId": "att-2"},
            },
        ],
    },
}


def _gmail_with(msg, attachment_bytes=b""):
    g = FakeGmail(get_results={msg["id"]: msg})
    g.set_attachment_data(base64.urlsafe_b64encode(attachment_bytes).decode("ascii"))
    return g


# ---- Gmail: attachment bytes + resolution ----

def test_get_attachment_bytes_decodes_base64url():
    g = _gmail_with(MSG, attachment_bytes=b"%PDF-1.4 binary")
    data = gc.get_attachment_bytes(g, "m1", "att-1")
    assert data == b"%PDF-1.4 binary"
    call = g.recorder["attachments_get"][0]
    assert call == {"userId": "me", "messageId": "m1", "id": "att-1"}


def test_resolve_attachment_by_id():
    g = _gmail_with(MSG)
    meta = gc.resolve_attachment(g, "m1", attachment_id="att-2")
    assert meta["filename"] == "logo.png"
    assert meta["mime_type"] == "image/png"


def test_resolve_attachment_by_filename():
    g = _gmail_with(MSG)
    meta = gc.resolve_attachment(g, "m1", filename="invoice.pdf")
    assert meta["attachment_id"] == "att-1"


def test_resolve_attachment_filename_wins_over_stale_id():
    # Gmail attachment IDs can change between requests; a stale id must not block a filename match.
    g = _gmail_with(MSG)
    meta = gc.resolve_attachment(g, "m1", attachment_id="STALE-ID", filename="invoice.pdf")
    assert meta["attachment_id"] == "att-1"


def test_resolve_attachment_unknown_id_raises():
    g = _gmail_with(MSG)
    with pytest.raises(ValueError):
        gc.resolve_attachment(g, "m1", attachment_id="nope")


def test_resolve_attachment_ambiguous_requires_disambiguation():
    g = _gmail_with(MSG)  # two attachments, none specified
    with pytest.raises(ValueError):
        gc.resolve_attachment(g, "m1")


def test_resolve_attachment_single_when_unspecified():
    single = {
        "id": "m2",
        "threadId": "t2",
        "payload": {
            "parts": [
                {
                    "mimeType": "application/pdf",
                    "filename": "only.pdf",
                    "body": {"size": 1, "attachmentId": "solo"},
                }
            ]
        },
    }
    g = _gmail_with(single)
    meta = gc.resolve_attachment(g, "m2")
    assert meta["attachment_id"] == "solo"


# ---- Drive: folder + upload ----

def test_find_or_create_folder_returns_existing():
    drive = FakeDrive(list_result={"files": [{"id": "folder-1", "name": "Gmail Attachments"}]})
    fid = dc.find_or_create_folder(drive, "Gmail Attachments")
    assert fid == "folder-1"
    assert "files_create" not in drive.recorder  # did not create


def test_find_or_create_folder_creates_when_absent():
    drive = FakeDrive(list_result={"files": []}, create_results=[{"id": "new-folder"}])
    fid = dc.find_or_create_folder(drive, "Gmail Attachments")
    assert fid == "new-folder"
    body = drive.recorder["files_create"][0]["body"]
    assert body["name"] == "Gmail Attachments"
    assert body["mimeType"] == "application/vnd.google-apps.folder"


def test_upload_bytes_creates_file_with_parent_and_media():
    drive = FakeDrive(
        create_results=[{"id": "f9", "name": "invoice.pdf", "webViewLink": "https://drive/f9"}]
    )
    out = dc.upload_bytes(drive, b"data", "invoice.pdf", "application/pdf", "folder-1")
    assert out == {
        "file_id": "f9",
        "name": "invoice.pdf",
        "web_view_link": "https://drive/f9",
    }
    call = drive.recorder["files_create"][0]
    assert call["body"]["name"] == "invoice.pdf"
    assert call["body"]["parents"] == ["folder-1"]
    assert call["media_body"] is not None


# ---- Orchestration ----

def test_download_attachment_to_drive_end_to_end():
    g = _gmail_with(MSG, attachment_bytes=b"PDFBYTES")
    drive = FakeDrive(
        list_result={"files": [{"id": "folder-1", "name": "Gmail Attachments"}]},
        create_results=[
            {"id": "uploaded-1", "name": "invoice.pdf", "webViewLink": "https://drive/u1"}
        ],
    )
    out = attachments.download_attachment_to_drive(g, drive, "m1", attachment_id="att-1")
    assert out["file_id"] == "uploaded-1"
    assert out["name"] == "invoice.pdf"
    assert out["web_view_link"] == "https://drive/u1"
    assert out["drive_folder"] == "Gmail Attachments"
    # The uploaded media should carry the attachment bytes fetched from Gmail.
    media = drive.recorder["files_create"][0]["media_body"]
    assert media.getbytes(0, media.size()) == b"PDFBYTES"
