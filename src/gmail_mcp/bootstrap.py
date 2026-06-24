"""One-time bootstrap: mint a Gmail+Drive refresh token and store it in SSM.

Runs a local browser consent for this server's three scopes (gmail.send + gmail.readonly +
drive.file) and writes the resulting credentials JSON to the SSM param the server reads at launch.

The OAuth client can come from either:
  * a Google "Desktop app" client_secret.json file (`--client-secrets-file`), or
  * an existing token already in SSM whose client_id/client_secret you want to reuse
    (`--client-secrets-ssm-param`).

Run via `python scripts/mint_token.py ...` (needs an active AWS session and a browser).
"""

import argparse
import json
import os

import boto3
from google_auth_oauthlib.flow import InstalledAppFlow

from . import SCOPES
from .auth import DEFAULT_PARAM, DEFAULT_REGION

DEST_PARAM = DEFAULT_PARAM
REGION = DEFAULT_REGION

_DEFAULT_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


def client_config_from_ssm(source_param, region=REGION, ssm_client=None):
    """Build an InstalledAppFlow client config by reusing client creds from an SSM token."""
    client = ssm_client or boto3.client("ssm", region_name=region)
    raw = client.get_parameter(Name=source_param, WithDecryption=True)["Parameter"]["Value"]
    info = json.loads(raw)
    return {
        "installed": {
            "client_id": info["client_id"],
            "client_secret": info["client_secret"],
            "auth_uri": info.get("auth_uri", _DEFAULT_AUTH_URI),
            "token_uri": info.get("token_uri", _DEFAULT_TOKEN_URI),
            "redirect_uris": ["http://localhost"],
        }
    }


def write_token_to_ssm(dest_param, creds_json, region=REGION, ssm_client=None):
    """Store the minted credentials JSON as an SSM SecureString (overwriting any prior value)."""
    client = ssm_client or boto3.client("ssm", region_name=region)
    client.put_parameter(
        Name=dest_param, Value=creds_json, Type="SecureString", Overwrite=True
    )


def _build_flow(client_secrets_file=None, client_secrets_ssm_param=None, region=REGION):
    """Construct the OAuth flow from a client_secret.json file or an SSM-stored client."""
    if client_secrets_file:
        return InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes=SCOPES)
    if client_secrets_ssm_param:
        config = client_config_from_ssm(client_secrets_ssm_param, region=region)
        return InstalledAppFlow.from_client_config(config, scopes=SCOPES)
    raise ValueError("Provide a client_secrets file or an SSM client-secrets param")


def mint(
    client_secrets_file=None,
    client_secrets_ssm_param=None,
    dest_param=DEST_PARAM,
    region=REGION,
    port=0,
):
    """Run the interactive consent flow and persist the token to SSM. Returns the credentials."""
    # Relax strict scope-equality so Google adding 'openid' doesn't abort the exchange.
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    flow = _build_flow(client_secrets_file, client_secrets_ssm_param, region)
    creds = flow.run_local_server(port=port, access_type="offline", prompt="consent")
    write_token_to_ssm(dest_param, creds.to_json(), region=region)
    return creds


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mint the gmail-mcp token into SSM.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--client-secrets-file",
        help="Path to a Google OAuth client_secret.json (Desktop app type).",
    )
    source.add_argument(
        "--client-secrets-ssm-param",
        help="SSM param holding an existing token whose client_id/client_secret to reuse.",
    )
    parser.add_argument("--dest-param", default=DEST_PARAM)
    parser.add_argument("--region", default=REGION, help="AWS region (default: standard AWS config)")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)

    print("Requesting scopes:\n  " + "\n  ".join(SCOPES))
    print("A browser window will open for Google consent...")
    creds = mint(
        client_secrets_file=args.client_secrets_file,
        client_secrets_ssm_param=args.client_secrets_ssm_param,
        dest_param=args.dest_param,
        region=args.region,
        port=args.port,
    )
    print(f"\nToken minted and written to {args.dest_param}.")
    print(f"Granted scopes: {list(getattr(creds, 'scopes', []) or [])}")


if __name__ == "__main__":
    main()
