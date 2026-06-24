"""Local attachment download — fetch bytes from Gmail, write to the local filesystem."""

import base64

import pytest

import gmail_mcp.attachments as attachments
from conftest import FakeGmail

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


def test_download_to_local_writes_file_and_returns_metadata(tmp_path):
    g = _gmail_with(MSG, attachment_bytes=b"%PDF-1.4 binary")
    out = attachments.download_attachment_to_local(
        g, "m1", str(tmp_path), filename="invoice.pdf"
    )
    written = tmp_path / "invoice.pdf"
    assert written.read_bytes() == b"%PDF-1.4 binary"
    assert out["name"] == "invoice.pdf"
    assert out["path"] == str(written)
    assert out["size_bytes"] == len(b"%PDF-1.4 binary")


def test_download_to_local_creates_missing_dest_dir(tmp_path):
    dest = tmp_path / "nested" / "dir"
    g = _gmail_with(MSG, attachment_bytes=b"DATA")
    out = attachments.download_attachment_to_local(
        g, "m1", str(dest), attachment_id="att-2"
    )
    assert (dest / "logo.png").read_bytes() == b"DATA"
    assert out["name"] == "logo.png"


def test_download_to_local_expands_user_home(tmp_path, monkeypatch):
    # ~ in dest_dir should expand to the user's home.
    monkeypatch.setenv("HOME", str(tmp_path))
    g = _gmail_with(MSG, attachment_bytes=b"DATA")
    out = attachments.download_attachment_to_local(
        g, "m1", "~/sub", filename="invoice.pdf"
    )
    assert out["path"] == str(tmp_path / "sub" / "invoice.pdf")
    assert (tmp_path / "sub" / "invoice.pdf").read_bytes() == b"DATA"


def test_download_to_local_sanitises_filename_against_traversal(tmp_path):
    evil = {
        "id": "m9",
        "threadId": "t9",
        "payload": {
            "parts": [
                {
                    "mimeType": "application/pdf",
                    "filename": "../../etc/evil.pdf",
                    "body": {"size": 1, "attachmentId": "solo"},
                }
            ]
        },
    }
    g = _gmail_with(evil, attachment_bytes=b"X")
    out = attachments.download_attachment_to_local(g, "m9", str(tmp_path))
    # Only the basename is used; nothing escapes dest_dir.
    assert out["path"] == str(tmp_path / "evil.pdf")
    assert (tmp_path / "evil.pdf").read_bytes() == b"X"
    assert not (tmp_path.parent.parent / "etc" / "evil.pdf").exists()


def test_download_to_local_ambiguous_requires_disambiguation(tmp_path):
    g = _gmail_with(MSG, attachment_bytes=b"DATA")  # two attachments, none specified
    with pytest.raises(ValueError):
        attachments.download_attachment_to_local(g, "m1", str(tmp_path))
