"""Phase 5: MCP wiring — tools registered and delegating to the core functions."""

import asyncio

import gmail_mcp.server as server


def test_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "send_email",
        "search_emails",
        "download_attachment",
        "download_attachment_local",
    }


def test_tools_have_descriptions():
    tools = asyncio.run(server.mcp.list_tools())
    for t in tools:
        assert t.description  # non-empty docstring surfaced to the model


def test_send_email_tool_delegates(monkeypatch):
    captured = {}
    monkeypatch.setattr(server.auth, "get_services", lambda: ("GMAIL", "DRIVE"))

    def fake_send(service, to, subject, body, cc=None, bcc=None, html=False):
        captured.update(
            service=service, to=to, subject=subject, body=body, cc=cc, bcc=bcc, html=html
        )
        return {"id": "x", "threadId": "t"}

    monkeypatch.setattr(server.gmail_client, "send_email", fake_send)
    out = server.send_email(to="a@b.com", subject="s", body="b")
    assert out == {"id": "x", "threadId": "t"}
    assert captured["service"] == "GMAIL"
    assert captured["to"] == "a@b.com"
    assert captured["cc"] is None  # empty string normalized to None
    assert captured["bcc"] is None


def test_search_tool_delegates(monkeypatch):
    monkeypatch.setattr(server.auth, "get_services", lambda: ("GMAIL", "DRIVE"))
    monkeypatch.setattr(
        server.gmail_client,
        "search_emails",
        lambda service, query, max_results=10: [{"id": "m1", "q": query, "n": max_results}],
    )
    out = server.search_emails(query="has:attachment", max_results=3)
    assert out == [{"id": "m1", "q": "has:attachment", "n": 3}]


def test_download_tool_delegates(monkeypatch):
    captured = {}
    monkeypatch.setattr(server.auth, "get_services", lambda: ("GMAIL", "DRIVE"))

    def fake_dl(gmail, drive, message_id, attachment_id=None, filename=None, folder_name=None):
        captured.update(
            gmail=gmail,
            drive=drive,
            message_id=message_id,
            attachment_id=attachment_id,
            filename=filename,
            folder_name=folder_name,
        )
        return {"file_id": "f", "web_view_link": "https://drive/f"}

    monkeypatch.setattr(server.attachments, "download_attachment_to_drive", fake_dl)
    out = server.download_attachment(message_id="m1", attachment_id="att-1")
    assert out["file_id"] == "f"
    assert captured["gmail"] == "GMAIL"
    assert captured["drive"] == "DRIVE"
    assert captured["message_id"] == "m1"
    assert captured["attachment_id"] == "att-1"
    assert captured["filename"] is None
    assert captured["folder_name"] == "Gmail Attachments"


def test_download_local_tool_delegates(monkeypatch):
    captured = {}
    monkeypatch.setattr(server.auth, "get_services", lambda: ("GMAIL", "DRIVE"))

    def fake_dl_local(gmail, message_id, dest_dir, attachment_id=None, filename=None):
        captured.update(
            gmail=gmail,
            message_id=message_id,
            dest_dir=dest_dir,
            attachment_id=attachment_id,
            filename=filename,
        )
        return {"path": "/tmp/x/invoice.pdf", "name": "invoice.pdf", "size_bytes": 4}

    monkeypatch.setattr(server.attachments, "download_attachment_to_local", fake_dl_local)
    out = server.download_attachment_local(message_id="m1", dest_dir="/tmp/x", filename="invoice.pdf")
    assert out["path"] == "/tmp/x/invoice.pdf"
    assert captured["gmail"] == "GMAIL"
    assert captured["message_id"] == "m1"
    assert captured["dest_dir"] == "/tmp/x"
    assert captured["filename"] == "invoice.pdf"
    assert captured["attachment_id"] is None  # empty string normalized to None


def test_main_runs_stdio_transport(monkeypatch):
    called = {}
    monkeypatch.setattr(server.mcp, "run", lambda transport=None: called.setdefault("t", transport))
    server.main()
    assert called["t"] == "stdio"
