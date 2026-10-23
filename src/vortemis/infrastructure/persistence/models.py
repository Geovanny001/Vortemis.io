from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DimProtocol(Base):
    __tablename__ = "dim_protocols"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)


class DimConnState(Base):
    __tablename__ = "dim_conn_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)


class FactNetworkFlow(Base):
    __tablename__ = "fact_network_flows"

    id: Mapped[int] = mapped_column(primary_key=True)
    flow_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    src_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    dst_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    src_port: Mapped[int] = mapped_column(nullable=False)
    dst_port: Mapped[int] = mapped_column(nullable=False)
    protocol_id: Mapped[int] = mapped_column(
        ForeignKey("dim_protocols.id"), nullable=False
    )
    conn_state_id: Mapped[int | None] = mapped_column(
        ForeignKey("dim_conn_states.id"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    orig_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resp_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    iat_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
