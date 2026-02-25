"""Tests for AsyncNewOrder."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from public_api_sdk.models.async_new_order import AsyncNewOrder
from public_api_sdk.models.new_order import WaitTimeoutError
from public_api_sdk.models.order import (
    Order,
    OrderStatus,
    OrderInstrument,
    OrderSide,
    OrderType,
)
from public_api_sdk.models.instrument_type import InstrumentType


def _make_order(status: OrderStatus, order_id: str = "order-123") -> Order:
    return Order(
        order_id=order_id,
        instrument=OrderInstrument(symbol="AAPL", type=InstrumentType.EQUITY),
        type=OrderType.LIMIT,
        side=OrderSide.BUY,
        status=status,
        quantity=Decimal("10"),
        limit_price=Decimal("150.00"),
        created_at=datetime.now(timezone.utc),
    )


class TestAsyncNewOrder:
    def setup_method(self) -> None:
        self.order_id = "order-123"
        self.account_id = "account-456"
        self.mock_client = MagicMock()
        self.mock_client.get_order = AsyncMock()
        self.mock_client.cancel_order = AsyncMock()

        self.async_new_order = AsyncNewOrder(
            order_id=self.order_id,
            account_id=self.account_id,
            client=self.mock_client,
        )

    def test_properties(self) -> None:
        assert self.async_new_order.order_id == self.order_id
        assert self.async_new_order.account_id == self.account_id

    def test_repr(self) -> None:
        assert self.order_id in repr(self.async_new_order)
        assert self.account_id in repr(self.async_new_order)

    @pytest.mark.asyncio
    async def test_get_status(self) -> None:
        self.mock_client.get_order.return_value = _make_order(OrderStatus.NEW)

        result = await self.async_new_order.get_status()

        assert result == OrderStatus.NEW
        self.mock_client.get_order.assert_called_once_with(
            order_id=self.order_id, account_id=self.account_id
        )

    @pytest.mark.asyncio
    async def test_get_details(self) -> None:
        order = _make_order(OrderStatus.NEW)
        self.mock_client.get_order.return_value = order

        result = await self.async_new_order.get_details()

        assert result == order
        self.mock_client.get_order.assert_called_once_with(
            order_id=self.order_id, account_id=self.account_id
        )

    @pytest.mark.asyncio
    async def test_wait_for_status_single_status(self) -> None:
        self.mock_client.get_order.return_value = _make_order(OrderStatus.FILLED)

        result = await self.async_new_order.wait_for_status(OrderStatus.FILLED, timeout=5)

        assert result.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_wait_for_status_multiple_statuses(self) -> None:
        self.mock_client.get_order.return_value = _make_order(OrderStatus.CANCELLED)

        result = await self.async_new_order.wait_for_status(
            [OrderStatus.FILLED, OrderStatus.CANCELLED], timeout=5
        )

        assert result.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_wait_for_status_timeout(self) -> None:
        self.mock_client.get_order.return_value = _make_order(OrderStatus.NEW)

        with pytest.raises(WaitTimeoutError) as exc_info:
            await self.async_new_order.wait_for_status(
                OrderStatus.FILLED, timeout=0.1, polling_interval=0.05
            )

        assert "Timeout waiting for order" in str(exc_info.value)
        assert self.order_id in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_fill(self) -> None:
        self.mock_client.get_order.return_value = _make_order(OrderStatus.FILLED)

        result = await self.async_new_order.wait_for_fill(timeout=5)

        assert result.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_wait_for_terminal_status(self) -> None:
        self.mock_client.get_order.return_value = _make_order(OrderStatus.REJECTED)

        result = await self.async_new_order.wait_for_terminal_status(timeout=5)

        assert result.status == OrderStatus.REJECTED

    @pytest.mark.asyncio
    async def test_cancel(self) -> None:
        await self.async_new_order.cancel()

        self.mock_client.cancel_order.assert_called_once_with(
            order_id=self.order_id, account_id=self.account_id
        )

    @pytest.mark.asyncio
    async def test_lock_is_asyncio_lock(self) -> None:
        """Verify the lock is asyncio.Lock, not threading.Lock."""
        assert isinstance(self.async_new_order._lock, asyncio.Lock)
