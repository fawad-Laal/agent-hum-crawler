"""Moltis FastAPI backend — Phase B modular API.

Import the app factory from :mod:`agent_hum_crawler.api.app`.
"""

from .app import create_app

__all__ = ["create_app"]
