"""Async Public API client for trading operations."""

from typing import AsyncGenerator, List, Optional

from .async_api_client import AsyncApiClient
from .async_auth_manager import AsyncAuthManager, AsyncApiKeyAuthProvider
from .models import (
    AccountsResponse,
    AsyncNewOrder,
    GreeksResponse,
    HistoryRequest,
    HistoryResponsePage,
    Instrument,
    InstrumentsRequest,
    InstrumentsResponse,
    InstrumentType,
    MultilegOrderRequest,
    MultilegOrderResult,
    OptionChainRequest,
    OptionChainResponse,
    OptionExpirationsRequest,
    OptionExpirationsResponse,
    OptionGreeks,
    Order,
    OrderInstrument,
    OrderRequest,
    OrderResponse,
    Portfolio,
    PreflightMultiLegRequest,
    PreflightMultiLegResponse,
    PreflightRequest,
    PreflightResponse,
    PriceChange,
    Quote,
)
from .exceptions import APIError

PROD_BASE_URL = "https://api.public.com"


class AsyncPublicApiClientConfiguration:
    """Configuration for AsyncPublicApiClient."""

    DEFAULT: "AsyncPublicApiClientConfiguration"

    def __init__(
        self,
        default_account_number: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize configuration.

        Args:
            default_account_number: Default account number for API calls
            base_url: Override the default production URL
        """
        self.base_url = base_url or PROD_BASE_URL
        self.default_account_number = default_account_number

    def get_base_url(self) -> str:
        return self.base_url


AsyncPublicApiClientConfiguration.DEFAULT = AsyncPublicApiClientConfiguration()


class AsyncPublicApiClient:
    """Async Public API client for trading operations."""

    def __init__(
        self,
        auth_config: "AsyncApiKeyAuthProvider",
        config: AsyncPublicApiClientConfiguration = AsyncPublicApiClientConfiguration.DEFAULT,
    ) -> None:
        """Initialize the async trading client.

        Args:
            auth_config: Async authentication configuration
            config: Configuration for the async API client
        """
        super().__init__()

        self.config = config

        # Create async HTTP client
        self.api_client = AsyncApiClient(base_url=config.get_base_url())

        # Create async auth manager
        self.auth_manager = AsyncAuthManager(auth_provider=auth_config)

    @property
    def api_endpoint(self) -> str:
        """The current API endpoint (base URL)."""
        return self.api_client.base_url

    @api_endpoint.setter
    def api_endpoint(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("api_endpoint must be a string URL")
        self.api_client.base_url = value.rstrip("/")

    async def close(self) -> None:
        """Close the client and release resources."""
        await self.api_client.close()

    async def __aenter__(self) -> "AsyncPublicApiClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    def _get_account_id(self, account_id: Optional[str] = None) -> str:
        """Get account ID from parameter or default."""
        if account_id:
            return account_id
        if self.config.default_account_number:
            return self.config.default_account_number
        raise ValueError("No account ID provided")

    async def get_accounts(self) -> AccountsResponse:
        """Get all accounts for the user.

        Returns:
            Account list response
        """
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.get("/userapigateway/trading/account")
        return AccountsResponse(**response)

    async def get_portfolio(self, account_id: Optional[str] = None) -> Portfolio:
        """Get portfolio for an account.

        Args:
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            Portfolio data including positions and balances
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.get(
            f"/userapigateway/trading/{account_id}/portfolio/v2"
        )
        return Portfolio(**response)

    async def get_history(
        self,
        history_request: Optional[HistoryRequest] = None,
        account_id: Optional[str] = None,
    ) -> HistoryResponsePage:
        """Get account history.

        Args:
            history_request: Optional history request with filters
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            Paginated history response
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.get(
            f"/userapigateway/trading/{account_id}/history",
            params=(
                history_request.model_dump(by_alias=True, exclude_none=True)
                if history_request
                else None
            ),
        )
        return HistoryResponsePage(**response)

    async def get_all_instruments(
        self,
        instruments_request: Optional[InstrumentsRequest] = None,
        account_id: Optional[str] = None,
    ) -> InstrumentsResponse:
        """Get all available instruments.

        Args:
            instruments_request: Optional instrument filters
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            List of available instruments
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.get(
            "/userapigateway/trading/instruments",
            params=(
                instruments_request.model_dump(by_alias=True, exclude_none=True)
                if instruments_request
                else None
            ),
        )
        return InstrumentsResponse(**response)

    async def get_instrument(
        self, 
        symbol: str, 
        instrument_type: InstrumentType
    ) -> Instrument:
        """Get instrument details.

        Args:
            symbol: Instrument symbol
            instrument_type: Type of instrument

        Returns:
            Instrument details
        """
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.get(
            f"/userapigateway/trading/instruments/{symbol}/{instrument_type.value}"
        )
        return Instrument(**response)

    async def get_quotes(
        self, 
        instruments: List[OrderInstrument], 
        account_id: Optional[str] = None
    ) -> List[Quote]:
        """Get quotes for multiple symbols.

        Args:
            instruments: List of instruments to get quotes for
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            List of quotes
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.post(
            f"/userapigateway/marketdata/{account_id}/quotes",
            json_data={
                "instruments": [instrument.model_dump() for instrument in instruments]
            },
        )
        quotes = response.get("quotes", [])
        return [Quote(**quote) for quote in quotes]

    async def get_option_expirations(
        self,
        expirations_request: OptionExpirationsRequest,
        account_id: Optional[str] = None,
    ) -> OptionExpirationsResponse:
        """Get option expiration dates.

        Args:
            expirations_request: Request with instrument details
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            Option expiration dates
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.post(
            f"/userapigateway/marketdata/{account_id}/option-expirations",
            json_data=expirations_request.model_dump(by_alias=True, exclude_none=True),
        )
        return OptionExpirationsResponse(**response)

    async def get_option_chain(
        self,
        option_chain_request: OptionChainRequest,
        account_id: Optional[str] = None,
    ) -> OptionChainResponse:
        """Get option chain for an instrument.

        Args:
            option_chain_request: Request with option chain parameters
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            Option chain response
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.post(
            f"/userapigateway/marketdata/{account_id}/option-chain",
            json_data=option_chain_request.model_dump(by_alias=True, exclude_none=True),
        )
        return OptionChainResponse(**response)

    async def get_option_greeks(
        self,
        osi_symbols: List[str],
        account_id: Optional[str] = None,
    ) -> GreeksResponse:
        """Get option Greeks for multiple symbols.

        Args:
            osi_symbols: List of OSI-normalized option symbols
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            Greeks response
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.get(
            f"/userapigateway/option-details/{account_id}/greeks",
            params={"osiSymbols": osi_symbols}
        )
        return GreeksResponse(**response)

    async def get_option_greek(
        self,
        osi_symbol: str,
        account_id: Optional[str] = None,
    ) -> OptionGreeks:
        """Get option Greeks for a single symbol.

        Args:
            osi_symbol: OSI-normalized option symbol
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            Option Greeks
        """
        greeks_response = await self.get_option_greeks(
            osi_symbols=[osi_symbol],
            account_id=account_id
        )
        if not greeks_response.greeks:
            raise ValueError(f"No greeks found for symbol: {osi_symbol}")
        return greeks_response.greeks[0]

    async def perform_preflight_calculation(
        self,
        preflight_request: PreflightRequest,
        account_id: Optional[str] = None,
    ) -> PreflightResponse:
        """Calculate estimated costs for a single-leg order.

        Args:
            preflight_request: Preflight request with order details
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            Preflight response with estimated costs
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.post(
            f"/userapigateway/trading/{account_id}/preflight/single-leg",
            json_data=preflight_request.model_dump(by_alias=True, exclude_none=True),
        )
        return PreflightResponse(**response)

    async def perform_multi_leg_preflight_calculation(
        self,
        preflight_request: PreflightMultiLegRequest,
        account_id: Optional[str] = None,
    ) -> PreflightMultiLegResponse:
        """Calculate estimated costs for a multi-leg order.

        Args:
            preflight_request: Preflight request with multi-leg order details
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            Preflight response with estimated costs
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.post(
            f"/userapigateway/trading/{account_id}/preflight/multi-leg",
            json_data=preflight_request.model_dump(by_alias=True, exclude_none=True),
        )
        return PreflightMultiLegResponse(**response)

    async def place_order(
        self,
        order_request: OrderRequest,
        account_id: Optional[str] = None,
    ) -> AsyncNewOrder:
        """Place a single-leg order.

        Args:
            order_request: Order request details
            account_id: Account ID

        Returns:
            AsyncNewOrder object for tracking
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.post(
            f"/userapigateway/trading/{account_id}/order",
            json_data=order_request.model_dump(by_alias=True, exclude_none=True),
        )
        order_response = OrderResponse(**response)

        return AsyncNewOrder(
            order_id=order_response.order_id,
            account_id=account_id,
            client=self,
        )

    async def place_multileg_order(
        self,
        order_request: MultilegOrderRequest,
        account_id: Optional[str] = None,
    ) -> AsyncNewOrder:
        """Place a multi-leg order.

        Args:
            order_request: Multi-leg order request details
            account_id: Account ID

        Returns:
            AsyncNewOrder object for tracking
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.post(
            f"/userapigateway/trading/{account_id}/order/multileg",
            json_data=order_request.model_dump(by_alias=True, exclude_none=True),
        )
        order_result = MultilegOrderResult(**response)

        return AsyncNewOrder(
            order_id=order_result.order_id,
            account_id=account_id,
            client=self,
        )

    async def get_order(
        self,
        order_id: str,
        account_id: Optional[str] = None,
    ) -> Order:
        """Get order details.

        Args:
            order_id: Order ID
            account_id: Account ID (optional if default_account_number is set)

        Returns:
            Order details
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        response = await self.api_client.get(
            f"/userapigateway/trading/{account_id}/order/{order_id}"
        )
        return Order(**response)

    async def cancel_order(
        self,
        order_id: str,
        account_id: Optional[str] = None,
    ) -> None:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel
            account_id: Account ID (optional if default_account_number is set)
        """
        account_id = self._get_account_id(account_id)
        await self.auth_manager.auth_provider.refresh_if_needed_async()
        await self.api_client.delete(f"/userapigateway/trading/{account_id}/order/{order_id}")


# For backward compatibility with auth_config
from .auth_config import ApiKeyAuthConfig, AuthConfig


def create_async_auth_config(api_secret_key: str) -> ApiKeyAuthConfig:
    """Create async auth configuration from API secret key.

    This returns a configuration object that can later be used to create
    an async auth provider bound to a specific AsyncApiClient instance,
    avoiding creation of any unused or "dummy" clients here.

    Args:
        api_secret_key: Public.com API secret key

    Returns:
        ApiKeyAuthConfig configured with the API key
    """
    return ApiKeyAuthConfig(api_secret_key=api_secret_key)


# Re-export for convenience
__all__ = [
    "AsyncPublicApiClient",
    "AsyncPublicApiClientConfiguration",
    "AsyncApiClient",
    "AsyncAuthManager",
    "AsyncApiKeyAuthProvider",
    "create_async_auth_config",
]
