"""Async price streaming with async generator support."""

import asyncio
import logging
from typing import AsyncGenerator, Callable, Dict, List, Optional, Set

from .async_public_api_client import AsyncPublicApiClient
from .models import (
    OrderInstrument,
    Quote,
)

logger = logging.getLogger(__name__)


class AsyncPriceStream:
    """Async price streaming with polling support."""

    def __init__(self, client: AsyncPublicApiClient):
        """Initialize async price stream.

        Args:
            client: AsyncPublicApiClient instance
        """
        self._client = client
        self._subscriptions: Dict[str, Set[str]] = {}  # subscription_id -> set of symbols
        self._last_quotes: Dict[str, Quote] = {}
        self._running: Set[str] = set()
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        instruments: List[OrderInstrument],
        polling_interval: float = 1.0,
    ) -> str:
        """Subscribe to price updates for instruments.

        Args:
            instruments: List of instruments to monitor
            polling_interval: Polling interval in seconds

        Returns:
            Subscription ID
        """
        import uuid
        subscription_id = str(uuid.uuid4())
        
        symbols = {inst.symbol for inst in instruments}
        async with self._lock:
            self._subscriptions[subscription_id] = symbols
            self._running.add(subscription_id)
        
        return subscription_id

    async def price_generator(
        self,
        subscription_id: str,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> AsyncGenerator[Dict[str, Quote], None]:
        """Generate price updates as async generator.

        Args:
            subscription_id: Subscription ID from subscribe()
            on_error: Optional callback invoked with the exception when a polling
                error occurs. If not provided, errors are logged and polling
                continues.

        Yields:
            Dictionary of symbol -> Quote for price changes
        """
        async with self._lock:
            if subscription_id not in self._subscriptions:
                raise ValueError(f"Unknown subscription: {subscription_id}")
            symbols = set(self._subscriptions[subscription_id])
        
        while True:
            async with self._lock:
                if subscription_id not in self._running:
                    break
                symbols = set(self._subscriptions.get(subscription_id, set()))
            
            try:
                # Build instruments list
                instruments = [
                    OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY)
                    for symbol in symbols
                ]
                
                # Fetch current quotes
                quotes = await self._client.get_quotes(instruments)
                
                # Check for changes
                changes = {}
                async with self._lock:
                    for quote in quotes:
                        symbol = quote.instrument.symbol
                        last_quote = self._last_quotes.get(symbol)
                        
                        if last_quote is None or last_quote.last_price != quote.last_price:
                            changes[symbol] = quote
                            self._last_quotes[symbol] = quote
                
                if changes:
                    yield changes
                    
            except Exception as e:
                logger.exception("Error fetching quotes for subscription %s", subscription_id)
                if on_error is not None:
                    on_error(e)
            
            # Wait before next poll
            await asyncio.sleep(1.0)

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from price updates.

        Args:
            subscription_id: Subscription ID to cancel
        """
        async with self._lock:
            self._running.discard(subscription_id)
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]

    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all price updates."""
        async with self._lock:
            self._running.clear()
            self._subscriptions.clear()

    def get_active_subscriptions(self) -> List[str]:
        """Get list of active subscription IDs."""
        return list(self._subscriptions.keys())


# Import InstrumentType for the price generator
from .models import InstrumentType
