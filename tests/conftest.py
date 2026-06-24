"""Shared fake Gmail/Drive service doubles for unit tests (no live Google calls)."""


class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeMessages:
    def __init__(self, recorder, send_result=None, list_result=None, get_results=None):
        self._rec = recorder
        self._send_result = send_result or {"id": "m1", "threadId": "t1"}
        self._list_result = list_result or {"messages": []}
        self._get_results = get_results or {}
        self._attachments = FakeAttachments(recorder)

    def send(self, userId=None, body=None):
        self._rec["send"] = {"userId": userId, "body": body}
        return _Exec(self._send_result)

    def list(self, userId=None, q=None, maxResults=None):
        self._rec.setdefault("list", []).append(
            {"userId": userId, "q": q, "maxResults": maxResults}
        )
        return _Exec(self._list_result)

    def get(self, userId=None, id=None, format=None):
        self._rec.setdefault("get", []).append({"userId": userId, "id": id, "format": format})
        return _Exec(self._get_results.get(id, {}))

    def attachments(self):
        return self._attachments


class FakeAttachments:
    def __init__(self, recorder):
        self._rec = recorder
        self.result = {"data": ""}

    def get(self, userId=None, messageId=None, id=None):
        self._rec.setdefault("attachments_get", []).append(
            {"userId": userId, "messageId": messageId, "id": id}
        )
        return _Exec(self.result)


class FakeUsers:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class FakeGmail:
    def __init__(self, send_result=None, list_result=None, get_results=None):
        self.recorder = {}
        self._messages = FakeMessages(self.recorder, send_result, list_result, get_results)

    def users(self):
        return FakeUsers(self._messages)

    def set_attachment_data(self, data_b64):
        self._messages._attachments.result = {"data": data_b64}


class FakeFiles:
    def __init__(self, recorder, list_result=None, create_results=None):
        self._rec = recorder
        self._list_result = list_result if list_result is not None else {"files": []}
        self._create_results = list(create_results or [])
        self._create_idx = 0

    def list(self, q=None, spaces=None, fields=None):
        self._rec.setdefault("files_list", []).append(
            {"q": q, "spaces": spaces, "fields": fields}
        )
        return _Exec(self._list_result)

    def create(self, body=None, media_body=None, fields=None):
        self._rec.setdefault("files_create", []).append(
            {"body": body, "media_body": media_body, "fields": fields}
        )
        if self._create_results:
            res = self._create_results[min(self._create_idx, len(self._create_results) - 1)]
        else:
            res = {
                "id": "file-id",
                "name": (body or {}).get("name"),
                "webViewLink": "https://drive.google.com/file/x",
            }
        self._create_idx += 1
        return _Exec(res)


class FakeDrive:
    def __init__(self, list_result=None, create_results=None):
        self.recorder = {}
        self._files = FakeFiles(self.recorder, list_result, create_results)

    def files(self):
        return self._files
