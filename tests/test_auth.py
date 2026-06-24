"""Phase 1: auth module — SSM-sourced Google credentials → Gmail + Drive services."""

import json

import gmail_mcp.auth as auth


class FakeSSM:
    def __init__(self, value):
        self._value = value
        self.calls = []

    def get_parameter(self, **kwargs):
        self.calls.append(kwargs)
        return {"Parameter": {"Value": self._value}}


def test_fetch_credentials_json_decrypts_and_parses():
    payload = {"client_id": "x", "refresh_token": "r", "client_secret": "s"}
    ssm = FakeSSM(json.dumps(payload))
    out = auth.fetch_credentials_json(param_name="/p", region="us-east-1", ssm_client=ssm)
    assert out == payload
    assert ssm.calls[0]["Name"] == "/p"
    assert ssm.calls[0]["WithDecryption"] is True


def test_build_credentials_refreshes_when_invalid(monkeypatch):
    refreshed = {"called": False}

    class FakeCreds:
        valid = False

        def refresh(self, request):
            refreshed["called"] = True
            self.valid = True

    monkeypatch.setattr(
        auth.Credentials,
        "from_authorized_user_info",
        classmethod(lambda cls, info, scopes=None: FakeCreds()),
    )
    auth.build_credentials({"refresh_token": "r"}, request=object())
    assert refreshed["called"] is True


def test_build_credentials_skips_refresh_when_valid(monkeypatch):
    class FakeCreds:
        valid = True

        def refresh(self, request):
            raise AssertionError("should not refresh a valid credential")

    monkeypatch.setattr(
        auth.Credentials,
        "from_authorized_user_info",
        classmethod(lambda cls, info, scopes=None: FakeCreds()),
    )
    creds = auth.build_credentials({"refresh_token": "r"}, request=object())
    assert creds.valid is True


def test_build_credentials_passes_required_scopes(monkeypatch):
    captured = {}

    class FakeCreds:
        valid = True

        def refresh(self, request):
            pass

    def fake_from_info(cls, info, scopes=None):
        captured["scopes"] = scopes
        return FakeCreds()

    monkeypatch.setattr(
        auth.Credentials, "from_authorized_user_info", classmethod(fake_from_info)
    )
    auth.build_credentials({"refresh_token": "r"})
    assert captured["scopes"] == auth.SCOPES


def test_get_services_builds_gmail_and_drive(monkeypatch):
    monkeypatch.setattr(auth, "fetch_credentials_json", lambda **kw: {"refresh_token": "r"})
    monkeypatch.setattr(auth, "build_credentials", lambda info: "CREDS")
    built = []

    def fake_build(name, version, credentials=None, cache_discovery=None):
        built.append((name, version, credentials))
        return f"{name}-service"

    monkeypatch.setattr(auth, "build", fake_build)
    gmail, drive = auth.get_services(param_name="/p", region="us-east-1")
    assert gmail == "gmail-service"
    assert drive == "drive-service"
    assert built == [("gmail", "v1", "CREDS"), ("drive", "v3", "CREDS")]
