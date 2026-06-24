"""Phase 2: send_email — MIME build, recipient validation, send, logging."""

import base64
import logging
from email import message_from_bytes

import pytest

import gmail_mcp.gmail_client as gc
from conftest import FakeGmail


def _decode_sent(gmail):
    raw = gmail.recorder["send"]["body"]["raw"]
    data = base64.urlsafe_b64decode(raw.encode("ascii"))
    return message_from_bytes(data)


def test_send_email_builds_message_and_calls_api():
    gmail = FakeGmail(send_result={"id": "abc", "threadId": "thr"})
    result = gc.send_email(gmail, to="alice@example.com", subject="Hi", body="Hello there")

    assert result == {"id": "abc", "threadId": "thr"}
    assert gmail.recorder["send"]["userId"] == "me"
    msg = _decode_sent(gmail)
    assert msg["To"] == "alice@example.com"
    assert msg["Subject"] == "Hi"
    assert "Hello there" in msg.get_payload(decode=True).decode("utf-8")
    assert msg.get_content_type() == "text/plain"


def test_send_email_html_sets_html_content_type():
    gmail = FakeGmail()
    gc.send_email(gmail, to="a@b.com", subject="s", body="<b>hi</b>", html=True)
    msg = _decode_sent(gmail)
    assert msg.get_content_type() == "text/html"


def test_send_email_includes_cc_and_bcc():
    gmail = FakeGmail()
    gc.send_email(
        gmail, to="a@b.com", subject="s", body="x", cc="c@d.com", bcc=["e@f.com", "g@h.com"]
    )
    msg = _decode_sent(gmail)
    assert msg["Cc"] == "c@d.com"
    assert msg["Bcc"] == "e@f.com, g@h.com"


def test_send_email_accepts_comma_string_and_list_recipients():
    gmail = FakeGmail()
    gc.send_email(gmail, to="a@b.com, c@d.com", subject="s", body="x")
    msg = _decode_sent(gmail)
    assert msg["To"] == "a@b.com, c@d.com"


def test_send_email_rejects_invalid_recipient():
    gmail = FakeGmail()
    with pytest.raises(ValueError):
        gc.send_email(gmail, to="not-an-email", subject="s", body="x")


def test_send_email_requires_a_recipient():
    gmail = FakeGmail()
    with pytest.raises(ValueError):
        gc.send_email(gmail, to="", subject="s", body="x")


def test_send_email_logs_the_send(caplog):
    gmail = FakeGmail(send_result={"id": "logme", "threadId": "t"})
    with caplog.at_level(logging.INFO, logger="gmail_mcp.send"):
        gc.send_email(gmail, to="a@b.com", subject="Subject Here", body="x")
    assert any("logme" in r.message and "Subject Here" in r.message for r in caplog.records)
