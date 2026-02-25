"""Tests for AsyncPriceStream."""

import asyncio
import logging
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
    async def test_price_generator_logs_exception_on_error(self):
        """Test price generator logs exceptions via the module logger."""
        client = _make_mock_client()
        error = RuntimeError("network failure")
        client.get_quotes = AsyncMock(side_effect=error)

        stream = AsyncPriceStream(client)
        instruments = [OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY)]
        subscription_id = await stream.subscribe(instruments)

        with patch("public_api_sdk.async_price_stream.logger") as mock_logger:
            # Unsubscribe after the first poll so the loop exits
            async def _run():
                async for _ in stream.price_generator(subscription_id):
                    pass  # pragma: no cover

            task = asyncio.create_task(_run())
            await asyncio.sleep(0.05)
            await stream.unsubscribe(subscription_id)
            await task

        mock_logger.exception.assert_called_once()
        assert "subscription" in mock_logger.exception.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_price_generator_calls_on_error_callback(self):
        """Test price generator invokes on_error callback with the exception."""
        client = _make_mock_client()
        error = RuntimeError("network failure")
        client.get_quotes = AsyncMock(side_effect=error)

        stream = AsyncPriceStream(client)
        instruments = [OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY)]
        subscription_id = await stream.subscribe(instruments)

        received_errors = []

        async def _run():
            async for _ in stream.price_generator(
                subscription_id, on_error=received_errors.append
            ):
                pass  # pragma: no cover

        task = asyncio.create_task(_run())
        await asyncio.sleep(0.05)
        await stream.unsubscribe(subscription_id)
        await task

        assert len(received_errors) >= 1
        assert received_errors[0] is error

    @pytest.mark.asyncio
    async def test_price_generator_no_callback_continues_after_error(self):
        """Test price generator continues polling after an error without a callback."""
        client = _make_mock_client()

        mock_quote = Mock()
        mock_quote.instrument.symbol = "AAPL"

        # Fail once, then succeed
        client.get_quotes = AsyncMock(
            side_effect=[RuntimeError("transient"), [mock_quote]]
        )

        stream = AsyncPriceStream(client)
        instruments = [OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY)]
        subscription_id = await stream.subscribe(instruments)

        changes = None
        with patch("public_api_sdk.async_price_stream.logger"):
            async for price_changes in stream.price_generator(subscription_id):
                changes = price_changes
                break

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
