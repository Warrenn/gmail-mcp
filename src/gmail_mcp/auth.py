"""Authentication: load Google credentials from AWS SSM and build Gmail + Drive services.

The refresh token lives in an SSM SecureString as an authorized_user / Credentials
JSON (client_id, client_secret, refresh_token, ...). We never write it to disk; it is fetched at
launch, used to build google credentials, and the Gmail/Drive API clients are built from those.
"""

import json
import os

import boto3
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from . import SCOPES

DEFAULT_PARAM = os.environ.get("GMAIL_MCP_SSM_PARAM", "/gmail-mcp/authorized-user-json")
# Region resolves from GMAIL_MCP_AWS_REGION, else standard AWS config (profile / AWS_REGION).
DEFAULT_REGION = os.environ.get("GMAIL_MCP_AWS_REGION")  # None -> boto3 resolves it


def fetch_credentials_json(param_name=DEFAULT_PARAM, region=DEFAULT_REGION, ssm_client=None):
    """Fetch and parse the credentials JSON from an SSM SecureString."""
    client = ssm_client or boto3.client("ssm", region_name=region)
    resp = client.get_parameter(Name=param_name, WithDecryption=True)
    return json.loads(resp["Parameter"]["Value"])


def build_credentials(info, request=None):
    """Build google Credentials from the authorized_user dict, refreshing if needed."""
    creds = Credentials.from_authorized_user_info(info, scopes=SCOPES)
    if not creds.valid:
        creds.refresh(request or Request())
    return creds


def get_services(param_name=DEFAULT_PARAM, region=DEFAULT_REGION, ssm_client=None):
    """Return (gmail_service, drive_service) authenticated for the configured account."""
    info = fetch_credentials_json(param_name=param_name, region=region, ssm_client=ssm_client)
    creds = build_credentials(info)
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return gmail, drive
