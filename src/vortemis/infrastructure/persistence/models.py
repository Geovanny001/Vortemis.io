from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, String
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


class DimMitreTactic(Base):
    __tablename__ = "dim_mitre_tactics"

    tactic_id: Mapped[int] = mapped_column(primary_key=True)
    mitre_id: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    tactic_name: Mapped[str] = mapped_column(String(50), nullable=False)


class SocUser(Base):
    __tablename__ = "soc_users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)


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
    tactic_id: Mapped[int | None] = mapped_column(
        ForeignKey("dim_mitre_tactics.tactic_id"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    orig_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resp_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    iat_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
