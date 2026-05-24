from contextlib import asynccontextmanager
from datetime import date
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.schemas import (
    AmountByCategory,
    AmountByPlatform,
    AssetSummaryResponse,
    CurrentAssetResponse,
    DailyMetricResponse,
    HealthResponse,
    MddResponse,
    PeriodReturnResponse,
    PlatformTimeseriesPoint,
    PortfolioTimeseriesPoint,
    TransactionResponse,
)
from app.crud.crud import (
    get_all_assets,
    get_asset_distribution_by_category,
    get_asset_distribution_by_platform,
    get_total_asset_value,
)
from app.crud.api_queries import (
    get_daily_metrics_for_api,
    get_portfolio_mdd,
    get_transactions_for_api,
)
from app.crud.metrics import get_portfolio_period_return
from app.crud.timeseries import (
    get_portfolio_timeseries,
    get_portfolio_timeseries_by_platform,
)
from app.utils.db import engine, test_connection
from models.models import Base


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        expected_tables = set(Base.metadata.tables.keys())
        existing_tables = set(inspect(engine).get_table_names())
        missing_tables = sorted(expected_tables - existing_tables)
        if missing_tables:
            logger.warning(
                "AMS API started with missing DB tables: %s. "
                "Run schema initialization before using data endpoints.",
                ", ".join(missing_tables),
            )
    except Exception as exc:
        logger.warning("AMS API could not verify DB schema at startup: %s", exc)
    yield


app = FastAPI(
    title="AMS Read API",
    description="Read-only API for AMS portfolio data.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    ok, message = test_connection()
    return HealthResponse(ok=ok, database=ok, message=message)


@app.get("/v1/assets/summary", response_model=AssetSummaryResponse)
def get_asset_summary(db: Session = Depends(get_db)) -> AssetSummaryResponse:
    by_platform = [
        AmountByPlatform(platform=row["platform"], amount_krw=float(row["amount"]))
        for row in get_asset_distribution_by_platform(db)
    ]
    by_category = [
        AmountByCategory(category=row["category"], amount_krw=float(row["amount"]))
        for row in get_asset_distribution_by_category(db)
    ]
    return AssetSummaryResponse(
        as_of=date.today(),
        currency="KRW",
        total_krw=float(get_total_asset_value(db)),
        by_platform=by_platform,
        by_category=by_category,
    )


@app.get("/v1/assets/current", response_model=list[CurrentAssetResponse])
def get_current_assets(db: Session = Depends(get_db)) -> list[CurrentAssetResponse]:
    assets = get_all_assets(db)
    return [
        CurrentAssetResponse(
            id=asset.id,
            platform=asset.platform.name if asset.platform else None,
            name=asset.name,
            symbol=asset.symbol,
            category=asset.category,
            exchange=asset.exchange,
            currency=asset.currency,
            current_price=asset.current_price,
            quantity=asset.quantity,
            evaluation_amount=asset.evaluation_amount,
            eval_amount_krw=asset.eval_amount_krw,
            avg_price=asset.avg_price,
            profit_loss=asset.profit_loss,
            profit_loss_rate=asset.profit_loss_rate,
            revision=asset.revision,
            updated_at=asset.updated_at,
        )
        for asset in assets
    ]


@app.get("/v1/returns/period", response_model=PeriodReturnResponse)
def get_period_return(
    days: Annotated[int, Query(gt=0)] = 30,
    reflect_flows: bool = True,
    db: Session = Depends(get_db),
) -> PeriodReturnResponse:
    return PeriodReturnResponse(
        days=days,
        reflect_flows=reflect_flows,
        return_rate_pct=get_portfolio_period_return(
            db, days=days, reflect_flows=reflect_flows
        ),
    )


@app.get("/v1/timeseries/portfolio", response_model=list[PortfolioTimeseriesPoint])
def get_portfolio_series(
    days: Annotated[int, Query(gt=0)] = 180,
    db: Session = Depends(get_db),
) -> list[PortfolioTimeseriesPoint]:
    return [
        PortfolioTimeseriesPoint(date=row["date"], total_krw=row["total_krw"])
        for row in get_portfolio_timeseries(db, days=days)
    ]


@app.get("/v1/timeseries/platforms", response_model=list[PlatformTimeseriesPoint])
def get_platform_series(
    days: Annotated[int, Query(gt=0)] = 180,
    db: Session = Depends(get_db),
) -> list[PlatformTimeseriesPoint]:
    return [
        PlatformTimeseriesPoint(
            date=row["date"],
            platform=row["platform"],
            total_krw=row["total_krw"],
        )
        for row in get_portfolio_timeseries_by_platform(db, days=days)
    ]


@app.get("/v1/metrics/daily", response_model=list[DailyMetricResponse])
def get_daily_metrics(
    days: Annotated[int, Query(gt=0)] = 180,
    platform: str | None = None,
    limit: Annotated[int, Query(gt=0, le=1000)] = 500,
    db: Session = Depends(get_db),
) -> list[DailyMetricResponse]:
    return [
        DailyMetricResponse(**row)
        for row in get_daily_metrics_for_api(
            db, days=days, platform=platform, limit=limit
        )
    ]


@app.get("/v1/transactions", response_model=list[TransactionResponse])
def get_transactions(
    days: Annotated[int, Query(gt=0)] = 30,
    transaction_type: Annotated[str | None, Query(alias="type")] = None,
    limit: Annotated[int, Query(gt=0, le=1000)] = 100,
    db: Session = Depends(get_db),
) -> list[TransactionResponse]:
    return [
        TransactionResponse(**row)
        for row in get_transactions_for_api(
            db, days=days, transaction_type=transaction_type, limit=limit
        )
    ]


@app.get("/v1/risk/mdd", response_model=MddResponse)
def get_mdd(
    days: Annotated[int, Query(gt=0)] = 30,
    db: Session = Depends(get_db),
) -> MddResponse:
    return MddResponse(**get_portfolio_mdd(db, days=days))
