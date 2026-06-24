"""Phase 0 smoke tests: the package imports and the core dependencies resolve."""


def test_package_imports():
    import gmail_mcp

    assert gmail_mcp.__version__ == "0.1.0"
    assert len(gmail_mcp.SCOPES) == 3


def test_core_dependencies_importable():
    # Fail loudly if the environment didn't resolve the runtime deps.
    import boto3  # noqa: F401
    import google.auth  # noqa: F401
    import googleapiclient  # noqa: F401
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
    from mcp.server.fastmcp import FastMCP  # noqa: F401
