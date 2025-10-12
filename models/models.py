from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class TransactionType(enum.Enum):
    BUY = "매수"
    SELL = "매도"
    TRANSFER_IN = "입금"
    TRANSFER_OUT = "출금"


class AssetCategory(enum.Enum):
    CRYPTO = "암호화폐"
    DOMESTIC_STOCK = "국내주식"
    FOREIGN_STOCK = "해외주식"
    CASH = "현금"
    STABLE_COIN = "스테이블코인"
    OTHERS = "기타"


class Platform(Base):
    """거래 플랫폼 (거래소, 증권사 등)"""

    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    assets = relationship("Asset", back_populates="platform")
    metrics = relationship("DailyAssetMetrics", back_populates="platform")


class Asset(Base):
    """자산 정보"""

    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    symbol = Column(String, index=True)
    category = Column(String, index=True)
    platform_id = Column(Integer, ForeignKey("platforms.id"))
    current_price = Column(Float)
    quantity = Column(Float)
    evaluation_amount = Column(Float)
    avg_price = Column(Float, nullable=True)  # 평균 매입 단가
    profit_loss = Column(Float, nullable=True)  # 평가 손익 금액
    profit_loss_rate = Column(Float, nullable=True)  # 평가 손익률
    currency = Column(String, nullable=True)  # 통화 코드
    exchange = Column(String, nullable=True)  # 거래소 코드
    eval_amount_krw = Column(Float, nullable=True)  # 원화 환산 평가금액
    revision = Column(Integer, nullable=False)  # 리비전 번호
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    platform = relationship("Platform", back_populates="assets")
    transactions = relationship("Transaction", back_populates="asset")

    __table_args__ = (
        Index(
            "idx_platform_revision",
            platform_id,
            revision.desc(),
        ),
    )


class Transaction(Base):
    """거래 내역"""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"))
    transaction_type = Column(String, index=True)
    price = Column(Float)
    quantity = Column(Float)
    amount = Column(Float)
    flow_amount_krw = Column(
        Float,
        nullable=True,
        comment="원화금액",
    )
    flow_fx_to_krw = Column(
        Float,
        nullable=True,
        comment="거래시점 환율",
    )
    memo = Column(String, nullable=True)
    transaction_date = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    asset = relationship("Asset", back_populates="transactions")


# DailyAssetMetrics 클래스 정의 추가
class DailyAssetMetrics(Base):
    """일일 자산 지표"""

    __tablename__ = "daily_asset_metrics"

    id = Column(Integer, primary_key=True)
    platform_id = Column(Integer, ForeignKey("platforms.id"))
    exchange = Column(String)
    symbol = Column(String)
    revision = Column(Integer)

    # 원래 통화 기준
    before_value = Column(Float)
    after_value = Column(Float)
    change_amount = Column(Float)
    return_rate = Column(Float)

    # 원화 환산 기준
    before_value_krw = Column(Float)
    after_value_krw = Column(Float)
    change_amount_krw = Column(Float)
    return_rate_krw = Column(Float)

    created_at = Column(DateTime, default=datetime.now)

    # 관계 설정
    platform = relationship("Platform", back_populates="metrics")

    __table_args__ = (
        Index("idx_daily_metrics_platform_revision", "platform_id", "revision"),
    )


class StableCoin(Base):
    """스테이블코인 정보"""

    __tablename__ = "stable_coins"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ExchangeRate(Base):
    """환율 정보"""

    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True)
    base_currency = Column(String(10), index=True)  # 기준 통화 (USD, JPY 등)
    target_currency = Column(String(10), index=True)  # 대상 통화 (KRW)
    rate = Column(Float)  # 환율
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        # 기준통화-대상통화 쌍은 유니크해야 함
        UniqueConstraint("base_currency", "target_currency", name="uix_currency_pair"),
    )
