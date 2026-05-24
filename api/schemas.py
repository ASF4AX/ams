from datetime import date, datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    ok: bool
    database: bool
    message: str


class AmountByPlatform(BaseModel):
    platform: str
    amount_krw: float


class AmountByCategory(BaseModel):
    category: str
    amount_krw: float


class AssetSummaryResponse(BaseModel):
    as_of: date
    currency: str
    total_krw: float
    by_platform: list[AmountByPlatform]
    by_category: list[AmountByCategory]


class CurrentAssetResponse(BaseModel):
    id: int
    platform: str | None
    name: str | None
    symbol: str | None
    category: str | None
    exchange: str | None
    currency: str | None
    current_price: float | None
    quantity: float | None
    evaluation_amount: float | None
    eval_amount_krw: float | None
    avg_price: float | None
    profit_loss: float | None
    profit_loss_rate: float | None
    revision: int
    updated_at: datetime | None


class PeriodReturnResponse(BaseModel):
    days: int
    reflect_flows: bool
    return_rate_pct: float | None


class PortfolioTimeseriesPoint(BaseModel):
    date: date
    total_krw: float


class PlatformTimeseriesPoint(BaseModel):
    date: date
    platform: str
    total_krw: float


class DailyMetricResponse(BaseModel):
    id: int
    platform: str | None
    exchange: str | None
    symbol: str | None
    revision: int | None
    before_value: float | None
    after_value: float | None
    change_amount: float | None
    return_rate: float | None
    before_value_krw: float | None
    after_value_krw: float | None
    change_amount_krw: float | None
    return_rate_krw: float | None
    created_at: datetime | None


class TransactionResponse(BaseModel):
    id: int
    asset_id: int | None
    asset_symbol: str | None
    asset_name: str | None
    platform: str | None
    transaction_type: str | None
    price: float | None
    quantity: float | None
    amount: float | None
    flow_amount_krw: float | None
    flow_fx_to_krw: float | None
    memo: str | None
    transaction_date: datetime | None


class MddResponse(BaseModel):
    days: int
    currency: str
    maximum_drawdown_pct: float | None
    peak_date: date | None
    trough_date: date | None
    peak_value_krw: float | None
    trough_value_krw: float | None
