"""Async Authentication manager for managing access tokens."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .async_api_client import AsyncApiClient


class AsyncAuthManager:
    """Async Authentication manager that delegates to auth providers"""

    def __init__(self, auth_provider: "AsyncAuthProvider") -> None:
        """Initialize the async authentication manager.

        Args:
            auth_provider: Async authentication provider (already initialized with AsyncApiClient)
        """
        super().__init__()

        self.auth_provider = auth_provider
        self.initialize_auth()

    def initialize_auth(self) -> None:
        """Initialize authentication by getting the first token."""
        try:
            # try to get an access token (will create one for API key auth)
            self.auth_provider.get_access_token()
        except ValueError:
            # for oauth, user needs to complete the flow first
            pass

    def refresh_token_if_needed(self) -> None:
        """Refresh the access token if it's expired or about to expire."""
        self.auth_provider.refresh_if_needed()

    def revoke_current_token(self) -> None:
        """Revoke the current access token and clear it from memory."""
        self.auth_provider.revoke_token()


class AsyncAuthProvider:
    """Abstract base class for async authentication providers."""

    def __init__(self, api_client: "AsyncApiClient") -> None:
        """Initialize the async auth provider.
        
        Args:
            api_client: Async API client for making HTTP requests
        """
        self.api_client = api_client

    def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token
        """

    def refresh_if_needed(self) -> None:
        """Refresh the access token if needed."""

    def revoke_token(self) -> None:
        """Revoke the current access token."""


class AsyncApiKeyAuthProvider(AsyncAuthProvider):
    """Async authentication provider for first party API key authentication."""

    def __init__(
        self, 
        api_client: "AsyncApiClient", 
        api_secret_key: str, 
        validity_minutes: int = 15
    ) -> None:
        """Initialize the async API key auth provider.

        Args:
            api_client: Async API client for making HTTP requests
            api_secret_key: API secret key
            validity_minutes: Token validity in minutes (5-1440)
        """
        super().__init__(api_client)

        if not 5 <= validity_minutes <= 1440:
            raise ValueError("Validity must be between 5 and 1440 minutes")

        self._secret = api_secret_key
        self._validity_minutes = validity_minutes

        self._access_token: Optional[str] = None
        self._access_token_expires_at: Optional[float] = None

    def get_access_token(self) -> str:
        """Get a valid access token, creating one if necessary."""
        if not self._is_token_valid():
            import asyncio
            asyncio.get_event_loop().run_until_complete(self._create_personal_access_token())
        return self._access_token or ""

    async def get_access_token_async(self) -> str:
        """Get a valid access token, creating one if necessary (async version)."""
        if not self._is_token_valid():
            await self._create_personal_access_token()
        return self._access_token or ""

    def refresh_if_needed(self) -> None:
        """Refresh the access token if it's expired or about to expire."""
        if not self._is_token_valid():
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in an async context, we need to handle differently
                    # For sync calls, just create new token
                    pass
                else:
                    loop.run_until_complete(self._create_personal_access_token())
            except RuntimeError:
                pass

    async def refresh_if_needed_async(self) -> None:
        """Refresh the access token if it's expired or about to expire (async version)."""
        if not self._is_token_valid():
            await self._create_personal_access_token()

    def revoke_token(self) -> None:
        """Revoke the current access token."""
        self._access_token = None
        self._access_token_expires_at = None
        self.api_client.remove_auth_header()

    def _is_token_valid(self) -> bool:
        """Check if the current access token is valid."""
        if not self._access_token or not self._access_token_expires_at:
            return False
        import time
        return time.time() < self._access_token_expires_at

    async def _create_personal_access_token(self) -> None:
        """Create a new access token using the API key."""
        import time
        
        payload = {
            "secret": self._secret,
            "validityInMinutes": self._validity_minutes,
        }

        response = await self.api_client.post(
            "/userapiauthservice/personal/access-tokens", json_data=payload
        )

        # store token and expiry time
        self._access_token = response.get("accessToken")
        if self._access_token:
            # calculate expiry time (subtract 5 minutes for safety buffer)
            expires_in_seconds = (self._validity_minutes - 5) * 60
            self._access_token_expires_at = time.time() + expires_in_seconds

            self.api_client.set_auth_header(self._access_token)
