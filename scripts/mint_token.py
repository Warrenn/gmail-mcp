#!/usr/bin/env python3
"""Thin CLI wrapper: mint the gmail-mcp Google token into SSM.

Usage (from the project root, with an active AWS session):
    uv run python scripts/mint_token.py
"""

from gmail_mcp.bootstrap import main

if __name__ == "__main__":
    main()
