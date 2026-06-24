"""Gmail operations: send_email (Phase 2). search_emails / attachments added in later phases."""

import base64
import logging
import re
from email.mime.text import MIMEText
from email.utils import getaddresses

logger = logging.getLogger("gmail_mcp.send")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _header(payload, name):
    """Case-insensitive lookup of a single header value, '' if absent."""
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _iter_parts(payload):
    """Yield every MIME part (including nested) under a message payload."""
    if not payload:
        return
    yield payload
    for part in payload.get("parts", []) or []:
        yield from _iter_parts(part)


def _extract_attachments(payload):
    """Collect attachment metadata (parts that have a filename and an attachmentId)."""
    attachments = []
    for part in _iter_parts(payload):
        filename = part.get("filename")
        body = part.get("body", {}) or {}
        attachment_id = body.get("attachmentId")
        if filename and attachment_id:
            attachments.append(
                {
                    "attachment_id": attachment_id,
                    "filename": filename,
                    "mime_type": part.get("mimeType", ""),
                    "size": body.get("size", 0),
                }
            )
    return attachments


def resolve_attachment(service, message_id, attachment_id=None, filename=None):
    """Resolve an attachment's metadata within a message by id or filename.

    If neither is given and the message has exactly one attachment, that one is used; otherwise a
    ValueError is raised asking the caller to disambiguate.
    """
    msg = (
        service.users().messages().get(userId="me", id=message_id, format="full").execute()
    )
    attachments = _extract_attachments(msg.get("payload", {}))
    if not attachments:
        raise ValueError(f"Message {message_id!r} has no attachments")

    # filename is the stable selector across requests; prefer it when given.
    if filename:
        matches = [a for a in attachments if a["filename"] == filename]
        if not matches:
            raise ValueError(f"No attachment named {filename!r} in message {message_id!r}")
        if len(matches) == 1:
            return matches[0]
        if attachment_id:
            for a in matches:
                if a["attachment_id"] == attachment_id:
                    return a
        raise ValueError(
            f"Multiple attachments named {filename!r}; specify attachment_id to disambiguate"
        )

    if attachment_id:
        for a in attachments:
            if a["attachment_id"] == attachment_id:
                return a
        raise ValueError(
            f"No attachment with id {attachment_id!r} in message {message_id!r}. "
            "Gmail attachment IDs can change between requests — prefer selecting by filename."
        )

    if len(attachments) == 1:
        return attachments[0]
    names = ", ".join(a["filename"] for a in attachments)
    raise ValueError(
        f"Message has multiple attachments ({names}); specify attachment_id or filename"
    )


def get_attachment_bytes(service, message_id, attachment_id):
    """Fetch and base64url-decode an attachment's raw bytes."""
    resp = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    return base64.urlsafe_b64decode(resp.get("data", "").encode("ascii"))


def search_emails(service, query, max_results=10):
    """Search messages by Gmail query; return summaries incl. attachment metadata."""
    listing = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    results = []
    for ref in listing.get("messages", []) or []:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=ref["id"], format="full")
            .execute()
        )
        payload = msg.get("payload", {})
        attachments = _extract_attachments(payload)
        results.append(
            {
                "id": msg.get("id", ref["id"]),
                "threadId": msg.get("threadId", ref.get("threadId", "")),
                "from": _header(payload, "From"),
                "to": _header(payload, "To"),
                "subject": _header(payload, "Subject"),
                "date": _header(payload, "Date"),
                "snippet": msg.get("snippet", ""),
                "has_attachments": bool(attachments),
                "attachments": attachments,
            }
        )
    return results


def _normalize_recipients(value):
    """Accept a string (optionally comma-separated) or list; return validated address list."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    addrs = [addr for _, addr in getaddresses(list(value)) if addr]
    for a in addrs:
        if not _EMAIL_RE.match(a):
            raise ValueError(f"Invalid email address: {a!r}")
    return addrs


def send_email(service, to, subject, body, cc=None, bcc=None, html=False):
    """Build a MIME message and send it via Gmail. Returns the API response (id, threadId)."""
    to_list = _normalize_recipients(to)
    if not to_list:
        raise ValueError("At least one 'to' recipient is required")
    cc_list = _normalize_recipients(cc)
    bcc_list = _normalize_recipients(bcc)

    msg = MIMEText(body, "html" if html else "plain", "utf-8")
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if bcc_list:
        msg["Bcc"] = ", ".join(bcc_list)
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()

    recipients = to_list + cc_list + bcc_list
    logger.info(
        "sent email id=%s to=%s subject=%r", result.get("id"), recipients, subject
    )
    return result
