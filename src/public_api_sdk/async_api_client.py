"""Async HTTP client with error handling and retry logic."""

import json
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession, TCPConnector

from .exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)


class AsyncApiClient:
    """Async HTTP client with error handling and retry logic."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 0.3,
    ) -> None:
        """Initialize the async base client.

        Args:
            base_url: Base URL for the API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            backoff_factor: Backoff factor for retry delays
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self._session: Optional[ClientSession] = None
        self._connector: Optional[TCPConnector] = None

    async def _get_session(self) -> ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            self._connector = TCPConnector(
                limit=self.max_retries,
                enable_cleanup_closed=True,
            )
            self._session = ClientSession(
                timeout=self.timeout,
                connector=self._connector,
            )
        return self._session

    def _get_version(self) -> str:
        """Get the package version."""
        try:
            from . import __version__
            return __version__
        except (ImportError, AttributeError):
            return "0.1.0"

    async def _get_headers(self) -> Dict[str, str]:
        """Get default headers."""
        version = self._get_version()
        return {
            "Content-Type": "application/json",
            "User-Agent": f"public-python-api-sdk-{version}",
            "X-App-Version": f"public-python-api-sdk-{version}",
        }

    def set_auth_header(self, token: str) -> None:
        """Set the `Authorization` header with a bearer token."""
        # Store for session creation
        self._auth_token = token

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get headers including auth if set."""
        headers = await self._get_headers()
        if hasattr(self, "_auth_token") and self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    def remove_auth_header(self) -> None:
        """Remove the Authorization header."""
        if hasattr(self, "_auth_token"):
            delattr(self, "_auth_token")

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        return urljoin(self.base_url + "/", endpoint.lstrip("/"))

    def _handle_response(self, response_data: Dict[str, Any], status_code: int) -> Dict[str, Any]:
        """Handle HTTP response and raise appropriate exceptions."""
        if status_code == 200:
            return response_data

        # extract error message from response
        error_message = response_data.get("message", "Unknown error")
        if isinstance(error_message, dict):
            error_message = str(error_message)

        # raise specific exceptions based on status code
        if status_code == 401:
            raise AuthenticationError(
                error_message, status_code, response_data
            )
        elif status_code == 400:
            raise ValidationError(error_message, status_code, response_data)
        elif status_code == 404:
            raise NotFoundError(error_message, status_code, response_data)
        elif status_code == 429:
            raise RateLimitError(
                error_message, status_code, None, response_data
            )
        elif 500 <= status_code < 600:
            raise ServerError(error_message, status_code, response_data)
        else:
            raise APIError(error_message, status_code, response_data)

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make async GET request."""
        session = await self._get_session()
        url = self._build_url(endpoint)
        headers = await self._get_auth_headers()

        async with session.get(url, params=params, headers=headers, **kwargs) as response:
            try:
                response_data = await response.json() if response.content_length else {}
            except json.JSONDecodeError:
                response_data = {"raw_content": await response.text()}

            return self._handle_response(response_data, response.status)

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make async POST request."""
        session = await self._get_session()
        url = self._build_url(endpoint)
        headers = await self._get_auth_headers()

        async with session.post(
            url,
            data=data,
            json=json_data,
            headers=headers,
            **kwargs,
        ) as response:
            try:
                response_data = await response.json() if response.content_length else {}
            except json.JSONDecodeError:
                response_data = {"raw_content": await response.text()}

            return self._handle_response(response_data, response.status)

    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make async PUT request."""
        session = await self._get_session()
        url = self._build_url(endpoint)
        headers = await self._get_auth_headers()

        async with session.put(
            url,
            data=data,
            json=json_data,
            headers=headers,
            **kwargs,
        ) as response:
            try:
                response_data = await response.json() if response.content_length else {}
            except json.JSONDecodeError:
                response_data = {"raw_content": await response.text()}

            return self._handle_response(response_data, response.status)

    async def delete(
        self,
        endpoint: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make async DELETE request."""
        session = await self._get_session()
        url = self._build_url(endpoint)
        headers = await self._get_auth_headers()

        async with session.delete(url, headers=headers, **kwargs) as response:
            try:
                response_data = await response.json() if response.content_length else {}
            except json.JSONDecodeError:
                response_data = {"raw_content": await response.text()}

            return self._handle_response(response_data, response.status)

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector:
            await self._connector.close()

    async def __aenter__(self) -> "AsyncApiClient":
        """Async context manager entry."""
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
