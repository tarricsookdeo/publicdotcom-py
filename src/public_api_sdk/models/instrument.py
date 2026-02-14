from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator

from .instrument_type import InstrumentType
from .order import OrderInstrument


class Trading(str, Enum):
    BUY_AND_SELL = "BUY_AND_SELL"
    LIQUIDATION_ONLY = "LIQUIDATION_ONLY"
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"  # Some APIs return this value


class CryptoInstrumentDetails(BaseModel):
    """Details specific to crypto instruments"""
    payload_type: str = Field(..., alias="payloadType")
    crypto_quantity_precision: Optional[int] = Field(..., alias="cryptoQuantityPrecision")
    crypto_price_precision: Optional[int] = Field(..., alias="cryptoPricePrecision")
    tradable_in_new_york: Optional[bool] = Field(..., alias="tradableInNewYork")


class Instrument(BaseModel):
    model_config = {"populate_by_name": True}

    instrument: OrderInstrument = Field(...)
    trading: Optional[Trading] = Field(None)
    fractional_trading: Optional[Trading] = Field(None, alias="fractionalTrading")
    option_trading: Optional[Trading] = Field(None, alias="optionTrading")
    option_spread_trading: Optional[Trading] = Field(None, alias="optionSpreadTrading")
    instrument_details: Optional[CryptoInstrumentDetails] = Field(
        None,
        alias="instrumentDetails",
        description="Additional details for crypto instruments"
    )

    @model_validator(mode="before")
    @classmethod
    def build_instrument_from_flat(cls, data: Any) -> Any:
        """Accept flat instrument data with symbol/type at top level."""
        if isinstance(data, dict) and "instrument" not in data and "symbol" in data:
            data = dict(data)
            data["instrument"] = {"symbol": data.pop("symbol"), "type": data.pop("type")}
        return data


class InstrumentsRequest(BaseModel):
    model_config = {"populate_by_name": True}

    type_filter: Optional[List[InstrumentType]] = Field(
        None,
        validation_alias=AliasChoices("type_filter", "typeFilter"),
        serialization_alias="typeFilter",
        description="optional set of security types to filter by",
    )
    trading_filter: Optional[List[Trading]] = Field(
        None,
        validation_alias=AliasChoices("trading_filter", "tradingFilter"),
        serialization_alias="tradingFilter",
        description="optional set of trading statuses to filter by",
    )
    fractional_trading_filter: Optional[List[Trading]] = Field(
        None,
        validation_alias=AliasChoices(
            "fractional_trading_filter", "fractionalTradingFilter"
        ),
        serialization_alias="fractionalTradingFilter",
        description="optional set of fractional trading statuses to filter by",
    )
    option_trading_filter: Optional[List[Trading]] = Field(
        None,
        validation_alias=AliasChoices("option_trading_filter", "optionTradingFilter"),
        serialization_alias="optionTradingFilter",
        description="optional set of option trading statuses to filter by",
    )
    option_spread_trading_filter: Optional[List[Trading]] = Field(
        None,
        validation_alias=AliasChoices(
            "option_spread_trading_filter", "optionSpreadTradingFilter"
        ),
        serialization_alias="optionSpreadTradingFilter",
        description="optional set of option spread trading statuses to filter by",
    )


class InstrumentsResponse(BaseModel):
    model_config = {"populate_by_name": True}

    instruments: List[Instrument] = Field(default_factory=list)
