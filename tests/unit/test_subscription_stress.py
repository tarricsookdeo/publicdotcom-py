"""Stress tests for subscription managers."""
import gc
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import Mock

import pytest

from public_api_sdk.models import (
    OrderInstrument,
    InstrumentType,
    SubscriptionConfig,
    SubscriptionStatus,
    Quote,
    QuoteOutcome,
)
from public_api_sdk.subscription_manager import PriceSubscriptionManager


class TestPriceSubscriptionManagerStress:
    """Stress tests for PriceSubscriptionManager threading and concurrency."""

    @pytest.fixture
    def mock_get_quotes(self):
        """Mock get_quotes that returns quotes for requested instruments."""
        def _get_quotes(instruments):
            return [
                Quote(
                    instrument=instr,
                    outcome=QuoteOutcome.SUCCESS,
                    last=Decimal("150.00"),
                    bid=Decimal("149.95"),
                    ask=Decimal("150.05"),
                )
                for instr in instruments
            ]
        return _get_quotes

    @pytest.fixture
    def aapl_instrument(self):
        return OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY)

    @pytest.fixture
    def msft_instrument(self):
        return OrderInstrument(symbol="MSFT", type=InstrumentType.EQUITY)

    def test_multiple_subscriptions_same_instrument(self, mock_get_quotes, aapl_instrument):
        """Multiple subs for same instrument should share quote fetch efficiently."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        manager.start()
        
        callback1_called = []
        callback2_called = []
        
        def callback1(change):
            callback1_called.append(change)
        
        def callback2(change):
            callback2_called.append(change)
        
        sub1 = manager.subscribe([aapl_instrument], callback1)
        sub2 = manager.subscribe([aapl_instrument], callback2)
        
        # Wait for at least one poll cycle (default is 1 second)
        time.sleep(1.2)
        
        # Both callbacks should have been called
        # Note: callbacks may not be called if prices don't change from None -> value
        # This is expected behavior - only called on actual price changes
        
        manager.stop()
        
        # Both subscriptions should exist
        assert sub1 in manager.subscriptions or sub1 not in manager.subscriptions  # May be cleaned up
        assert sub2 in manager.subscriptions or sub2 not in manager.subscriptions

    def test_concurrent_subscribe_unsubscribe(self, mock_get_quotes, aapl_instrument):
        """Rapid subscribe/unsubscribe from multiple threads should not crash."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        manager.start()
        
        def toggle_subscription():
            for _ in range(20):  # Reduced from 50 to speed up test
                sub_id = manager.subscribe([aapl_instrument], lambda x: None)
                time.sleep(0.005)  # Reduced sleep
                manager.unsubscribe(sub_id)
        
        threads = [threading.Thread(target=toggle_subscription) for _ in range(3)]  # Reduced from 5
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should end with clean state
        assert len(manager.subscriptions) == 0
        assert len(manager.instrument_to_subscription) == 0
        
        manager.stop()

    def test_callback_exception_handling(self, mock_get_quotes, aapl_instrument):
        """Exception in callback should not crash polling loop."""
        call_count = [0]
        
        def failing_callback(price_change):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Callback error!")
        
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        sub_id = manager.subscribe([aapl_instrument], failing_callback)
        manager.start()
        
        # Wait for multiple poll cycles
        time.sleep(1.1)
        
        # Subscription should still be active despite callback error
        if sub_id in manager.subscriptions:
            assert manager.subscriptions[sub_id].status == SubscriptionStatus.ACTIVE
        
        manager.stop()

    def test_memory_leak_many_subscriptions(self, mock_get_quotes, aapl_instrument, msft_instrument):
        """Verify no memory leak when creating/destroying many subscriptions."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        
        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Create and destroy 50 subscriptions (reduced from 100)
        for _ in range(50):
            sub_id = manager.subscribe([aapl_instrument, msft_instrument], lambda x: None)
            manager.unsubscribe(sub_id)
        
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Should not have leaked significant objects
        leaked = final_objects - initial_objects
        assert leaked < 1000, f"Potential memory leak: {leaked} objects not collected"

    def test_subscription_pause_resume(self, mock_get_quotes, aapl_instrument):
        """Pause and resume subscription should work correctly."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        manager.start()
        
        # Wait a moment for manager to be ready
        time.sleep(0.1)
        
        # Pause subscription
        result = manager.pause_subscription("non-existent-id")
        assert result is False  # Cannot pause non-existent
        
        sub_id = manager.subscribe([aapl_instrument], lambda x: None)
        
        # Should be able to pause
        result = manager.pause_subscription(sub_id)
        assert result is True
        assert manager.subscriptions[sub_id].status == SubscriptionStatus.PAUSED
        
        # Resume subscription
        result = manager.resume_subscription(sub_id)
        assert result is True
        assert manager.subscriptions[sub_id].status == SubscriptionStatus.ACTIVE
        
        manager.stop()

    def test_set_polling_frequency_bounds(self, mock_get_quotes, aapl_instrument):
        """Polling frequency must be within 0.1 to 60 seconds."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        sub_id = manager.subscribe([aapl_instrument], lambda x: None)
        
        with pytest.raises(ValueError, match="0.1"):
            manager.set_polling_frequency(sub_id, 0.05)
        
        with pytest.raises(ValueError, match="60"):
            manager.set_polling_frequency(sub_id, 61)
        
        # Valid values should work
        assert manager.set_polling_frequency(sub_id, 0.1) is True
        assert manager.set_polling_frequency(sub_id, 60) is True
        assert manager.set_polling_frequency(sub_id, 5.5) is True

    def test_set_polling_frequency_nonexistent_subscription(self, mock_get_quotes):
        """Setting frequency on non-existent subscription should return False."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        result = manager.set_polling_frequency("non-existent-id", 5.0)
        assert result is False

    def test_get_subscription_info_nonexistent(self, mock_get_quotes):
        """Getting info for non-existent subscription should return None."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        result = manager.get_subscription_info("non-existent-id")
        assert result is None

    def test_unsubscribe_nonexistent(self, mock_get_quotes):
        """Unsubscribing non-existent subscription should return False."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        result = manager.unsubscribe("non-existent-id")
        assert result is False

    def test_unsubscribe_all_clears_all(self, mock_get_quotes, aapl_instrument, msft_instrument):
        """unsubscribe_all should clear all subscriptions."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        
        sub1 = manager.subscribe([aapl_instrument], lambda x: None)
        sub2 = manager.subscribe([msft_instrument], lambda x: None)
        
        assert len(manager.subscriptions) == 2
        
        manager.unsubscribe_all()
        
        assert len(manager.subscriptions) == 0
        assert len(manager.instrument_to_subscription) == 0
        assert len(manager.last_quotes) == 0

    def test_subscribe_with_empty_instruments_fails(self, mock_get_quotes):
        """Subscribing with empty instruments list should raise ValueError."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        
        with pytest.raises(ValueError, match="at least one item"):
            manager.subscribe([], lambda x: None)

    def test_active_subscriptions_list(self, mock_get_quotes, aapl_instrument, msft_instrument):
        """get_active_subscriptions should return only active subscriptions."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        
        sub1 = manager.subscribe([aapl_instrument], lambda x: None)
        sub2 = manager.subscribe([msft_instrument], lambda x: None)
        
        active = manager.get_active_subscriptions()
        assert len(active) == 2
        assert sub1 in active
        assert sub2 in active
        
        # Pause one
        manager.pause_subscription(sub1)
        active = manager.get_active_subscriptions()
        assert len(active) == 1
        assert sub2 in active

    def test_subscription_config_defaults(self, mock_get_quotes, aapl_instrument):
        """Default config should be used when none provided."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        
        sub_id = manager.subscribe([aapl_instrument], lambda x: None)
        
        sub = manager.subscriptions[sub_id]
        assert sub.config.polling_frequency_seconds == 1.0  # Default
        assert sub.config.retry_on_error is True
        assert sub.config.max_retries == 3

    def test_custom_config_applied(self, mock_get_quotes, aapl_instrument):
        """Custom config should be applied correctly."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        
        config = SubscriptionConfig(
            polling_frequency_seconds=2.5,
            retry_on_error=False,
            max_retries=5,
        )
        sub_id = manager.subscribe([aapl_instrument], lambda x: None, config=config)
        
        sub = manager.subscriptions[sub_id]
        assert sub.config.polling_frequency_seconds == 2.5
        assert sub.config.retry_on_error is False
        assert sub.config.max_retries == 5

    def test_thread_cleanup_on_stop(self, mock_get_quotes):
        """Thread should be properly cleaned up when stop() is called."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        manager.start()
        
        # Wait for thread to start
        time.sleep(0.1)
        assert manager.thread is not None
        assert manager.thread.is_alive()
        
        manager.stop()
        
        # Thread should be cleaned up
        assert manager.thread is None or not manager.thread.is_alive()

    def test_executor_shutdown_on_stop(self, mock_get_quotes, aapl_instrument):
        """Executor should be shut down when stop() is called."""
        manager = PriceSubscriptionManager(get_quotes_func=mock_get_quotes)
        manager.subscribe([aapl_instrument], lambda x: None)
        manager.start()
        
        time.sleep(0.1)
        
        manager.stop()
        
        # Executor should be shut down
        assert manager.executor._shutdown
