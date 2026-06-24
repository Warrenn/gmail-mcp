"""Phase 3: search_emails — list + get, extract headers + attachment metadata."""

import gmail_mcp.gmail_client as gc
from conftest import FakeGmail

MSG_WITH_ATTACHMENT = {
    "id": "m1",
    "threadId": "t1",
    "snippet": "Here is the file you asked for",
    "payload": {
        "mimeType": "multipart/mixed",
        "headers": [
            {"name": "From", "value": "Bob <bob@example.com>"},
            {"name": "To", "value": "me@example.com"},
            {"name": "Subject", "value": "Invoice attached"},
            {"name": "Date", "value": "Mon, 01 Jan 2026 10:00:00 +0000"},
        ],
        "parts": [
            {"mimeType": "text/plain", "body": {"size": 20, "data": "aGVsbG8="}},
            {
                "mimeType": "application/pdf",
                "filename": "invoice.pdf",
                "body": {"size": 12345, "attachmentId": "att-1"},
            },
        ],
    },
}

MSG_PLAIN = {
    "id": "m2",
    "threadId": "t2",
    "snippet": "just a note",
    "payload": {
        "mimeType": "text/plain",
        "headers": [
            {"name": "From", "value": "a@b.com"},
            {"name": "Subject", "value": "Hello"},
        ],
        "body": {"size": 5, "data": "aGk="},
    },
}

MSG_NESTED = {
    "id": "m3",
    "threadId": "t3",
    "snippet": "nested",
    "payload": {
        "mimeType": "multipart/mixed",
        "headers": [{"name": "Subject", "value": "Nested"}],
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain", "body": {"size": 3}},
                    {
                        "mimeType": "image/png",
                        "filename": "photo.png",
                        "body": {"size": 999, "attachmentId": "att-9"},
                    },
                ],
            }
        ],
    },
}


def _gmail(messages):
    list_result = {"messages": [{"id": m["id"], "threadId": m["threadId"]} for m in messages]}
    get_results = {m["id"]: m for m in messages}
    return FakeGmail(list_result=list_result, get_results=get_results)


def test_search_returns_metadata_and_attachment_for_each_message():
    gmail = _gmail([MSG_WITH_ATTACHMENT, MSG_PLAIN])
    results = gc.search_emails(gmail, "has:attachment")

    assert [r["id"] for r in results] == ["m1", "m2"]
    first = results[0]
    assert first["from"] == "Bob <bob@example.com>"
    assert first["to"] == "me@example.com"
    assert first["subject"] == "Invoice attached"
    assert first["date"] == "Mon, 01 Jan 2026 10:00:00 +0000"
    assert first["snippet"] == "Here is the file you asked for"
    assert first["has_attachments"] is True
    assert first["attachments"] == [
        {
            "attachment_id": "att-1",
            "filename": "invoice.pdf",
            "mime_type": "application/pdf",
            "size": 12345,
        }
    ]


def test_search_message_without_attachment():
    gmail = _gmail([MSG_PLAIN])
    results = gc.search_emails(gmail, "from:a@b.com")
    assert results[0]["has_attachments"] is False
    assert results[0]["attachments"] == []
    assert results[0]["subject"] == "Hello"
    assert results[0]["to"] == ""  # missing header -> empty string


def test_search_finds_attachments_in_nested_parts():
    gmail = _gmail([MSG_NESTED])
    results = gc.search_emails(gmail, "x")
    assert results[0]["attachments"] == [
        {
            "attachment_id": "att-9",
            "filename": "photo.png",
            "mime_type": "image/png",
            "size": 999,
        }
    ]


def test_search_passes_query_and_max_results():
    gmail = _gmail([MSG_PLAIN])
    gc.search_emails(gmail, "subject:hello", max_results=5)
    call = gmail.recorder["list"][0]
    assert call["userId"] == "me"
    assert call["q"] == "subject:hello"
    assert call["maxResults"] == 5


def test_search_empty_results():
    gmail = FakeGmail(list_result={"messages": []})
    assert gc.search_emails(gmail, "nothing") == []
