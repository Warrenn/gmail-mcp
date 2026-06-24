"""Phase 6: bootstrap helpers — build client config from SSM, write minted token to SSM.

The interactive consent (run_local_server) is not unit-tested; the surrounding I/O is.
"""

import json

import gmail_mcp.bootstrap as bootstrap


class FakeSSM:
    def __init__(self, value=None):
        self._value = value
        self.gets = []
        self.puts = []

    def get_parameter(self, **kw):
        self.gets.append(kw)
        return {"Parameter": {"Value": self._value}}

    def put_parameter(self, **kw):
        self.puts.append(kw)
        return {"Version": 1}


def test_client_config_from_ssm_builds_installed_config():
    src = json.dumps(
        {
            "client_id": "cid",
            "client_secret": "csec",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )
    ssm = FakeSSM(src)
    cfg = bootstrap.client_config_from_ssm(source_param="/src", region="us-east-1", ssm_client=ssm)
    installed = cfg["installed"]
    assert installed["client_id"] == "cid"
    assert installed["client_secret"] == "csec"
    assert installed["token_uri"] == "https://oauth2.googleapis.com/token"
    assert installed["auth_uri"].startswith("https://")
    assert installed["redirect_uris"]
    assert ssm.gets[0]["Name"] == "/src"
    assert ssm.gets[0]["WithDecryption"] is True


def test_client_config_defaults_token_uri_when_missing():
    ssm = FakeSSM(json.dumps({"client_id": "c", "client_secret": "s"}))
    cfg = bootstrap.client_config_from_ssm(source_param="/src", ssm_client=ssm)
    assert cfg["installed"]["token_uri"].startswith("https://")


def test_write_token_to_ssm_puts_securestring_overwrite():
    ssm = FakeSSM()
    bootstrap.write_token_to_ssm("/dest", '{"token":"x"}', region="us-east-1", ssm_client=ssm)
    put = ssm.puts[0]
    assert put["Name"] == "/dest"
    assert put["Value"] == '{"token":"x"}'
    assert put["Type"] == "SecureString"
    assert put["Overwrite"] is True


def test_default_params_align_with_auth_module():
    import gmail_mcp.auth as auth

    # The bootstrap must write to the exact param the server reads from.
    assert bootstrap.DEST_PARAM == auth.DEFAULT_PARAM


def test_build_flow_requires_a_client_source():
    import pytest

    with pytest.raises(ValueError):
        bootstrap._build_flow()
