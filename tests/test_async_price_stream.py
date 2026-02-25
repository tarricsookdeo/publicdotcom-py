"""Tests for AsyncPriceStream."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from public_api_sdk import AsyncPriceStream, AsyncPublicApiClient
from public_api_sdk.async_public_api_client import AsyncApiKeyAuthProvider
from public_api_sdk.models import (
    InstrumentType,
    OrderInstrument,
    Quote,
)


def _make_mock_client() -> AsyncPublicApiClient:
    """Create a mock AsyncPublicApiClient."""
    client = Mock(spec=AsyncPublicApiClient)
    client.get_quotes = AsyncMock(return_value=[])
    return client


class TestAsyncPriceStream:
    """Test AsyncPriceStream functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_creates_subscription(self):
        """Test subscribe creates a new subscription."""
        client = _make_mock_client()
        stream = AsyncPriceStream(client)
        
        instruments = [
            OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY),
            OrderInstrument(symbol="TSLA", type=InstrumentType.EQUITY),
        ]
        
        subscription_id = await stream.subscribe(instruments)
        
        assert subscription_id is not None
        assert subscription_id in stream.get_active_subscriptions()

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscription(self):
        """Test unsubscribe removes an existing subscription."""
        client = _make_mock_client()
        stream = AsyncPriceStream(client)
        
        instruments = [OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY)]
        subscription_id = await stream.subscribe(instruments)
        
        await stream.unsubscribe(subscription_id)
        
        assert subscription_id not in stream.get_active_subscriptions()

    @pytest.mark.asyncio
    async def test_unsubscribe_all_removes_all(self):
        """Test unsubscribe_all removes all subscriptions."""
        client = _make_mock_client()
        stream = AsyncPriceStream(client)
        
        instruments1 = [OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY)]
        instruments2 = [OrderInstrument(symbol="TSLA", type=InstrumentType.EQUITY)]
        
        await stream.subscribe(instruments1)
        await stream.subscribe(instruments2)
        
        await stream.unsubscribe_all()
        
        assert len(stream.get_active_subscriptions()) == 0

    @pytest.mark.asyncio
    async def test_price_generator_yields_changes(self):
        """Test price generator yields price changes."""
        client = _make_mock_client()
        
        # Create mock quote
        mock_quote = Mock(spec=Quote)
        mock_quote.instrument.symbol = "AAPL"
        mock_quote.last_price = Mock()
        mock_quote.last_price.last_price = "150.00"
        
        client.get_quotes = AsyncMock(return_value=[mock_quote])
        
        stream = AsyncPriceStream(client)
        instruments = [OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY)]
        
        subscription_id = await stream.subscribe(instruments)
        
        # Collect one iteration
        changes = None
        async for price_changes in stream.price_generator(subscription_id):
            changes = price_changes
            break  # Only want one update
        
        assert changes is not None
        assert "AAPL" in changes

    @pytest.mark.asyncio
    async def test_price_generator_unknown_subscription(self):
        """Test price generator raises for unknown subscription."""
        client = _make_mock_client()
        stream = AsyncPriceStream(client)
        
        with pytest.raises(ValueError, match="Unknown subscription"):
            # Need to iterate to trigger the error
            async for _ in stream.price_generator("invalid-id"):
                pass

    def test_get_active_subscriptions(self):
        """Test getting list of active subscriptions."""
        client = _make_mock_client()
        stream = AsyncPriceStream(client)
        
        assert stream.get_active_subscriptions() == []


class TestAsyncPriceStreamIntegration:
    """Integration tests for AsyncPriceStream."""

    @pytest.mark.asyncio
    async def test_multiple_instruments(self):
        """Test subscribing to multiple instruments."""
        client = _make_mock_client()
        
        mock_quote_aapl = Mock(spec=Quote)
        mock_quote_aapl.instrument.symbol = "AAPL"
        mock_quote_aapl.last_price = Mock()
        mock_quote_aapl.last_price.last_price = "150.00"
        
        mock_quote_tsla = Mock(spec=Quote)
        mock_quote_tsla.instrument.symbol = "TSLA"
        mock_quote_tsla.last_price = Mock()
        mock_quote_tsla.last_price.last_price = "200.00"
        
        client.get_quotes = AsyncMock(return_value=[mock_quote_aapl, mock_quote_tsla])
        
        stream = AsyncPriceStream(client)
        instruments = [
            OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY),
            OrderInstrument(symbol="TSLA", type=InstrumentType.EQUITY),
        ]
        
        subscription_id = await stream.subscribe(instruments)
        
        # Get one update
        async for changes in stream.price_generator(subscription_id):
            assert "AAPL" in changes
            assert "TSLA" in changes
            break
        
        await stream.unsubscribe(subscription_id)
