"""
Example: Async Public API Client Usage

This example demonstrates how to use the async Public API client
for concurrent trading operations.
"""

import asyncio

from public_api_sdk import (
    AsyncPublicApiClient,
    AsyncPublicApiClientConfiguration,
    create_async_auth_config,
    InstrumentType,
    OrderInstrument,
)


async def main():
    """Main async example."""
    
    # Initialize the async client
    auth = create_async_auth_config(api_secret_key="YOUR_API_SECRET_KEY")
    config = AsyncPublicApiClientConfiguration(
        default_account_number="YOUR_ACCOUNT_NUMBER"
    )
    
    async with AsyncPublicApiClient(auth_config=auth, config=config) as client:
        
        # Example 1: Get account and portfolio concurrently
        print("Fetching account and portfolio concurrently...")
        accounts, portfolio = await asyncio.gather(
            client.get_accounts(),
            client.get_portfolio()
        )
        
        print(f"Accounts: {[a.account_id for a in accounts.accounts]}")
        print(f"Portfolio equity: {portfolio.equity}")
        
        # Example 2: Get quotes for multiple symbols
        print("\nFetching quotes for multiple symbols...")
        instruments = [
            OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY),
            OrderInstrument(symbol="MSFT", type=InstrumentType.EQUITY),
            OrderInstrument(symbol="GOOGL", type=InstrumentType.EQUITY),
        ]
        
        quotes = await client.get_quotes(instruments)
        
        for quote in quotes:
            symbol = quote.instrument.symbol
            price = quote.last_price.last_price
            print(f"  {symbol}: ${price}")
        
        # Example 3: Streaming prices (async generator)
        print("\nStreaming prices...")
        price_stream = client._price_stream = __import__(
            'public_api_sdk.async_price_stream', 
            fromlist=['AsyncPriceStream']
        ).AsyncPriceStream(client)
        
        await price_stream.subscribe(instruments)
        
        async for price_changes in price_stream.price_generator(
            price_stream.get_active_subscriptions()[0]
        ):
            for symbol, quote in price_changes.items():
                print(f"  {symbol}: ${quote.last_price.last_price}")
            
            # Just get one update for this example
            break
        
        # Cleanup
        await price_stream.unsubscribe_all()
        
    print("\nDone!")


async def concurrent_orders_example():
    """Example of placing multiple orders concurrently."""
    
    from decimal import Decimal
    from public_api_sdk.models import OrderRequest, OrderSide, OrderType
    
    auth = create_async_auth_config(api_secret_key="YOUR_API_SECRET_KEY")
    config = AsyncPublicApiClientConfiguration(
        default_account_number="YOUR_ACCOUNT_NUMBER"
    )
    
    async with AsyncPublicApiClient(auth_config=auth, config=config) as client:
        
        # Create multiple order requests
        orders = [
            OrderRequest(
                order_id=f"order-{i}",
                instrument=OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY),
                order_side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("10"),
            )
            for i, symbol in enumerate(["AAPL", "MSFT", "GOOGL"])
        ]
        
        # Place orders concurrently
        print("Placing multiple orders concurrently...")
        results = await asyncio.gather(
            *[client.place_order(order) for order in orders]
        )
        
        for result in results:
            print(f"  Order placed: {result.order_id}")


if __name__ == "__main__":
    asyncio.run(main())
    # asyncio.run(concurrent_orders_example())  # Uncomment for order example
