import asyncio
import time
from typing import TYPE_CHECKING, Optional, List, Union

from .order import Order, OrderStatus
from .new_order import WaitTimeoutError

if TYPE_CHECKING:
    from ..async_public_api_client import AsyncPublicApiClient


class AsyncNewOrder:
    """
    Represents a newly placed order with async methods for tracking and managing the order.

    This object is returned by AsyncPublicApiClient.place_order() and
    AsyncPublicApiClient.place_multileg_order(). All order-management methods are
    coroutines so they integrate naturally with asyncio-based code.

    Note: Synchronous subscription-based tracking (subscribe_updates / unsubscribe)
    is not available for async clients. Use wait_for_status() or poll get_status()
    instead.
    """

    def __init__(
        self,
        order_id: str,
        account_id: str,
        client: "AsyncPublicApiClient",
    ):
        """
        Initialize an AsyncNewOrder instance.

        Args:
            order_id: The order ID
            account_id: The account ID
            client: Reference to the AsyncPublicApiClient
        """
        self._order_id = order_id
        self._account_id = account_id
        self._client = client
        self._last_known_status: Optional[OrderStatus] = None
        self._lock = asyncio.Lock()

    @property
    def order_id(self) -> str:
        return self._order_id

    @property
    def account_id(self) -> str:
        return self._account_id

    async def get_status(self) -> OrderStatus:
        """
        Get the current order status by fetching from the API.

        Returns:
            Current order status
        """
        order = await self._client.get_order(
            order_id=self._order_id, account_id=self._account_id
        )
        async with self._lock:
            self._last_known_status = order.status
        return order.status

    async def get_details(self) -> Order:
        """
        Get the full order details by fetching from the API.

        Returns:
            Current order details including status, fills, etc.
        """
        order = await self._client.get_order(
            order_id=self._order_id, account_id=self._account_id
        )
        async with self._lock:
            self._last_known_status = order.status
        return order

    async def wait_for_status(
        self,
        target_status: Union[OrderStatus, List[OrderStatus]],
        timeout: Optional[float] = None,
        polling_interval: float = 1.0,
    ) -> Order:
        """
        Wait asynchronously for the order to reach a specific status.

        Args:
            target_status: Status to wait for, or list of statuses
            timeout: Maximum time to wait in seconds (None for no timeout)
            polling_interval: How often to check status (seconds)

        Returns:
            Order details when target status is reached

        Raises:
            WaitTimeoutError: If timeout is exceeded

        Example:
            ```python
            # Wait for order to be filled
            order = await new_order.wait_for_status(OrderStatus.FILLED, timeout=60)

            # Wait for any terminal status
            order = await new_order.wait_for_status(
                [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED],
                timeout=30
            )
            ```
        """
        if isinstance(target_status, OrderStatus):
            target_statuses = [target_status]
        else:
            target_statuses = target_status

        start_time = time.monotonic()

        while True:
            order = await self.get_details()

            if order.status in target_statuses:
                return order

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    raise WaitTimeoutError(
                        f"Timeout waiting for order {self._order_id} to reach "
                        f"status {target_statuses}. Current status: {order.status}"
                    )

            await asyncio.sleep(polling_interval)

    async def wait_for_fill(self, timeout: Optional[float] = None) -> Order:
        """
        Wait for the order to be filled.

        Args:
            timeout: Maximum time to wait in seconds (None for no timeout)

        Returns:
            Order details when filled

        Raises:
            WaitTimeoutError: If timeout is exceeded

        Example:
            ```python
            try:
                order = await new_order.wait_for_fill(timeout=60)
                print(f"Order filled at {order.average_price}")
            except WaitTimeoutError:
                print("Order not filled within timeout")
            ```
        """
        return await self.wait_for_status(OrderStatus.FILLED, timeout=timeout)

    async def wait_for_terminal_status(self, timeout: Optional[float] = None) -> Order:
        """
        Wait for the order to reach a terminal status (filled, cancelled, rejected, expired).

        Args:
            timeout: Maximum time to wait in seconds (None for no timeout)

        Returns:
            Order details when terminal status is reached

        Raises:
            WaitTimeoutError: If timeout is exceeded
        """
        terminal_statuses = [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.REPLACED,
        ]
        return await self.wait_for_status(terminal_statuses, timeout=timeout)

    async def cancel(self) -> None:
        """
        Cancel the order.

        Note: Cancellation is asynchronous. Use wait_for_status() to confirm
        the cancellation.

        Example:
            ```python
            await new_order.cancel()
            # wait for cancellation to be confirmed
            order = await new_order.wait_for_status(OrderStatus.CANCELLED, timeout=10)
            ```
        """
        await self._client.cancel_order(
            order_id=self._order_id, account_id=self._account_id
        )

    def __repr__(self) -> str:
        return f"AsyncNewOrder(order_id={self._order_id}, account_id={self._account_id})"
