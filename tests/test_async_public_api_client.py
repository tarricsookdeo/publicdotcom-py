"""Tests for AsyncPublicApiClient API methods.

All tests patch AsyncApiClient and AsyncAuthManager at construction time so no real HTTP
calls are made.
"""

import asyncio
from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

from public_api_sdk import (
    AsyncPublicApiClient,
    AsyncPublicApiClientConfiguration,
    create_async_auth_config,
)
from public_api_sdk.async_public_api_client import AsyncApiKeyAuthProvider
from public_api_sdk.models import (
    Account,
    AccountType,
    AccountsResponse,
    HistoryRequest,
    HistoryResponsePage,
    Instrument,
    InstrumentType,
    OrderInstrument,
    Portfolio,
    Quote,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ACCOUNT = "ACC123"
_VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"


def _make_async_client(default_account: Optional[str] = _ACCOUNT) -> AsyncPublicApiClient:
    """Return an AsyncPublicApiClient with AsyncApiClient and AsyncAuthManager patched."""
    with patch("public_api_sdk.async_public_api_client.AsyncApiClient"), \
         patch("public_api_sdk.async_public_api_client.AsyncAuthManager"):
        config = AsyncPublicApiClientConfiguration(default_account_number=default_account)
        
        # Create a mock auth provider
        mock_auth_provider = Mock(spec=AsyncApiKeyAuthProvider)
        mock_auth_provider.refresh_if_needed_async = AsyncMock()
        
        client = AsyncPublicApiClient(
            auth_config=mock_auth_provider,
            config=config,
        )
        
        # Replace api_client with a mock
        client.api_client = AsyncMock()
        client.api_client.get = AsyncMock(return_value={})
        client.api_client.post = AsyncMock(return_value={})
        client.api_client.delete = AsyncMock()
        client.api_client.close = AsyncMock()
        
    return client


def _make_account_response() -> dict:
    """Return a mocked account response."""
    return {
        "accounts": [
            {
                "account_id": "ACC123",
                "account_type": "BROKERAGE",
                "brokerage_account_type": "MARGIN",
                "options_level": "LEVEL_2",
                "trade_permissions": ["EQUITY", "OPTIONS"],
            }
        ]
    }


def _make_portfolio_response() -> dict:
    """Return a mocked portfolio response."""
    return {
        "account_id": "ACC123",
        "account_type": "BROKERAGE",
        "equity": [
            {
                "type": "STOCK",
                "value": "10000.00",
                "percentage_of_portfolio": "50.0",
            },
            {
                "type": "CASH",
                "value": "10000.00",
                "percentage_of_portfolio": "50.0",
            },
        ],
        "positions": [],
        "buying_power": {
            "cash_only_buying_power": "5000.00",
            "buying_power": "10000.00",
            "options_buying_power": "5000.00",
        },
    }


def _make_quotes_response() -> dict:
    """Return a mocked quotes response."""
    return {
        "quotes": [
            {
                "instrument": {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "type": "EQUITY",
                },
                "last_price": {
                    "last_price": "150.00",
                },
                "bid": {"bid_price": "149.90"},
                "ask": {"ask_price": "150.10"},
                "volume": 1000000,
            }
        ]
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAsyncApiClient:
    """Test AsyncPublicApiClient initialization and configuration."""

    def test_default_configuration(self):
        """Test client initializes with default configuration."""
        with patch("public_api_sdk.async_public_api_client.AsyncApiClient"), \
             patch("public_api_sdk.async_public_api_client.AsyncAuthManager"):
            
            mock_auth = Mock(spec=AsyncApiKeyAuthProvider)
            client = AsyncPublicApiClient(auth_config=mock_auth)
            
            assert client.config.base_url == "https://api.public.com"
            assert client.config.default_account_number is None

    def test_custom_configuration(self):
        """Test client initializes with custom configuration."""
        with patch("public_api_sdk.async_public_api_client.AsyncApiClient"), \
             patch("public_api_sdk.async_public_api_client.AsyncAuthManager"):
            
            mock_auth = Mock(spec=AsyncApiKeyAuthProvider)
            config = AsyncPublicApiClientConfiguration(
                default_account_number="TEST123",
                base_url="https://test.api.public.com"
            )
            client = AsyncPublicApiClient(
                auth_config=mock_auth,
                config=config
            )
            
            assert client.config.base_url == "https://test.api.public.com"
            assert client.config.default_account_number == "TEST123"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test client works as async context manager."""
        client = _make_async_client()
        client.api_client.close = AsyncMock()
        
        async with client:
            pass
        
        client.api_client.close.assert_called_once()

    def test_api_endpoint_property(self):
        """Test api_endpoint property getter and setter."""
        client = _make_async_client()
        
        # Test getter
        assert client.api_endpoint == "https://api.public.com"
        
        # Test setter
        client.api_endpoint = "https://custom.api.com"
        assert client.api_endpoint == "https://custom.api.com"
        
        # Test type validation
        with pytest.raises(TypeError):
            client.api_endpoint = 123  # type: ignore


class TestAsyncGetAccounts:
    """Test async get_accounts method."""

    @pytest.mark.asyncio
    async def test_get_accounts_returns_response(self):
        """Test get_accounts returns properly parsed AccountsResponse."""
        client = _make_async_client()
        client.api_client.get = AsyncMock(return_value=_make_account_response())
        
        result = await client.get_accounts()
        
        assert isinstance(result, AccountsResponse)
        assert len(result.accounts) == 1
        assert result.accounts[0].account_id == "ACC123"

    @pytest.mark.asyncio
    async def test_get_accounts_calls_api(self):
        """Test get_accounts makes correct API call."""
        client = _make_async_client()
        client.api_client.get = AsyncMock(return_value=_make_account_response())
        
        await client.get_accounts()
        
        client.api_client.get.assert_called_once_with("/userapigateway/trading/account")


class TestAsyncGetPortfolio:
    """Test async get_portfolio method."""

    @pytest.mark.asyncio
    async def test_get_portfolio_returns_response(self):
        """Test get_portfolio returns properly parsed Portfolio."""
        client = _make_async_client()
        client.api_client.get = AsyncMock(return_value=_make_portfolio_response())
        
        result = await client.get_portfolio()
        
        assert isinstance(result, Portfolio)
        assert result.account_id == "ACC123"

    @pytest.mark.asyncio
    async def test_get_portfolio_with_account_id(self):
        """Test get_portfolio uses provided account_id."""
        client = _make_async_client()
        client.api_client.get = AsyncMock(return_value=_make_portfolio_response())
        
        await client.get_portfolio(account_id="OTHER_ACC")
        
        call_args = client.api_client.get.call_args
        assert "OTHER_ACC" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_portfolio_uses_default_account(self):
        """Test get_portfolio uses default account when not provided."""
        client = _make_async_client()
        client.api_client.get = AsyncMock(return_value=_make_portfolio_response())
        
        await client.get_portfolio()
        
        call_args = client.api_client.get.call_args
        assert "ACC123" in call_args[0][0]

    def test_get_portfolio_requires_account_id(self):
        """Test get_portfolio raises when no account_id available."""
        client = _make_async_client(default_account=None)
        
        with pytest.raises(ValueError, match="No account ID"):
            asyncio.get_event_loop().run_until_complete(client.get_portfolio())


class TestAsyncGetQuotes:
    """Test async get_quotes method."""

    @pytest.mark.asyncio
    async def test_get_quotes_returns_list(self):
        """Test get_quotes returns list of Quotes."""
        client = _make_async_client()
        client.api_client.post = AsyncMock(return_value=_make_quotes_response())
        
        instruments = [OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY)]
        result = await client.get_quotes(instruments)
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].instrument.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_quotes_post_data(self):
        """Test get_quotes sends correct data."""
        client = _make_async_client()
        client.api_client.post = AsyncMock(return_value=_make_quotes_response())
        
        instruments = [OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY)]
        await client.get_quotes(instruments)
        
        call_args = client.api_client.post.call_args
        assert "quotes" in call_args.kwargs.get("json_data", {})


class TestAsyncPlaceOrder:
    """Test async order placement."""

    @pytest.mark.asyncio
    async def test_place_order_returns_new_order(self):
        """Test place_order returns NewOrder object."""
        client = _make_async_client()
        client.api_client.post = AsyncMock(return_value={
            "order_id": _VALID_UUID,
        })
        
        from public_api_sdk.models import OrderRequest, OrderSide, OrderType
        
        order_request = OrderRequest(
            order_id=_VALID_UUID,
            instrument=OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY),
            order_side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("10"),
        )
        
        result = await client.place_order(order_request)
        
        assert result.order_id == _VALID_UUID
        assert result.account_id == _ACCOUNT


class TestAsyncCancelOrder:
    """Test async order cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_order_calls_delete(self):
        """Test cancel_order makes DELETE request."""
        client = _make_async_client()
        client.api_client.delete = AsyncMock()
        
        await client.cancel_order(order_id=_VALID_UUID)
        
        client.api_client.delete.assert_called_once()


class TestAsyncContextManager:
    """Test async context manager functionality."""

    @pytest.mark.asyncio
    async def test_async_with_statement(self):
        """Test client works with async 'with' statement."""
        client = _make_async_client()
        client.api_client.close = AsyncMock()
        
        async with client as ctx:
            assert ctx is client
        
        client.api_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_method(self):
        """Test close() method calls api_client.close()."""
        client = _make_async_client()
        client.api_client.close = AsyncMock()
        
        await client.close()
        
        client.api_client.close.assert_called_once()


class TestCreateAsyncAuthConfig:
    """Test create_async_auth_config helper function."""

    def test_creates_auth_provider(self):
        """Test helper creates properly configured auth provider."""
        auth = create_async_auth_config("test_key")
        
        assert isinstance(auth, AsyncApiKeyAuthProvider)
        assert auth._secret == "test_key"
