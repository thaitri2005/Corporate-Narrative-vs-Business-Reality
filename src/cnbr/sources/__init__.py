"""External-source adapters."""

from cnbr.sources.sec import SecClient, validate_sec_user_agent

__all__ = ["SecClient", "validate_sec_user_agent"]
