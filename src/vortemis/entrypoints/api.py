import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.application.use_cases.flow_normalizer import FlowNormalizerUseCase
from vortemis.infrastructure.persistence.models import (
    DimConnState,
    DimMitreTactic,
    DimProtocol,
    FactNetworkFlow,
    SocUser,
)
from vortemis.infrastructure.persistence.postgres_repository import (
    EXFILTRATION_BYTES_THRESHOLD,
    PostgresFlowRepository,
)
from vortemis.infrastructure.security import verify_password
from vortemis.infrastructure.zeek.telemetry_source import ZeekTelemetrySource

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql+asyncpg://vortemis:vortemis@localhost:5432/vortemis"
JWT_SECRET_ENV = "JWT_SECRET"
DEFAULT_JWT_SECRET = "vortemis-dev-secret-change-me"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60
LOG_FILE_ENV = "LOG_FILE"
DEFAULT_LOG_FILE = "conn.log"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str


class ThresholdUpdate(BaseModel):
    epsilon_threshold: float = Field(ge=0.1, le=0.99)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        for websocket in list(self._connections):
            await websocket.send_json(message)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database_url = os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.session_factory = session_factory
    app.state.epsilon_threshold = 0.5
    yield
    await engine.dispose()


app = FastAPI(title="Vortemis SOC API", version="1.0.0", lifespan=lifespan)

_bearer = HTTPBearer(auto_error=False)


def _jwt_secret() -> str:
    return os.getenv(JWT_SECRET_ENV, DEFAULT_JWT_SECRET)


def _create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(UTC) + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
        )
    try:
        return jwt.decode(
            credentials.credentials, _jwt_secret(), algorithms=[JWT_ALGORITHM]
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from exc


def require_role(*roles: str) -> Callable[..., dict]:
    def dependency(payload: Annotated[dict, Depends(require_auth)]) -> dict:
        if payload.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role"
            )
        return payload

    return dependency


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, request: Request) -> LoginResponse:
    async with request.app.state.session_factory() as session:
        user = await session.scalar(
            select(SocUser).where(SocUser.username == credentials.username)
        )
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )
    return LoginResponse(
        access_token=_create_token(user.username, user.role),
        token_type="bearer",
        role=user.role,
    )


@app.get("/api/v1/health")
async def health(request: Request) -> dict:
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(select(1))
        database = "ok"
    except Exception:
        database = "unavailable"
    return {"status": "ok", "database": database, "service": "vortemis-api"}


@app.get("/api/v1/metrics/summary")
async def metrics_summary(
    request: Request,
    _auth: Annotated[dict, Depends(require_auth)],
) -> dict:
    async with request.app.state.session_factory() as session:
        total_flows = (
            await session.scalar(select(func.count()).select_from(FactNetworkFlow)) or 0
        )
        total_anomalies = (
            await session.scalar(
                select(func.count())
                .select_from(FactNetworkFlow)
                .where(FactNetworkFlow.is_anomaly.is_(True))
            )
            or 0
        )
        exfiltration_alerts = (
            await session.scalar(
                select(func.count())
                .select_from(FactNetworkFlow)
                .where(FactNetworkFlow.orig_bytes > EXFILTRATION_BYTES_THRESHOLD)
            )
            or 0
        )
        mitre_rows = (
            await session.execute(
                select(DimMitreTactic.tactic_name, func.count(FactNetworkFlow.id))
                .join(
                    FactNetworkFlow,
                    FactNetworkFlow.tactic_id == DimMitreTactic.tactic_id,
                )
                .group_by(DimMitreTactic.tactic_name)
            )
        ).all()
        protocol_rows = (
            await session.execute(
                select(DimProtocol.name, func.count(FactNetworkFlow.id))
                .join(FactNetworkFlow, FactNetworkFlow.protocol_id == DimProtocol.id)
                .group_by(DimProtocol.name)
            )
        ).all()
    return {
        "total_flows": total_flows,
        "total_anomalies": total_anomalies,
        "exfiltration_alerts": exfiltration_alerts,
        "mitre_breakdown": dict(mitre_rows),
        "protocol_breakdown": dict(protocol_rows),
    }


@app.get("/api/v1/flows")
async def list_flows(
    request: Request,
    _auth: Annotated[dict, Depends(require_auth)],
    src_ip: str | None = None,
    dst_port: int | None = None,
    protocol: str | None = None,
    only_anomalies: bool = False,
    limit: int = 100,
) -> dict:
    statement = (
        select(
            FactNetworkFlow,
            DimProtocol.name.label("protocol_name"),
            DimMitreTactic.mitre_id,
            DimConnState.name.label("conn_state_name"),
        )
        .join(DimProtocol, FactNetworkFlow.protocol_id == DimProtocol.id)
        .outerjoin(DimMitreTactic, FactNetworkFlow.tactic_id == DimMitreTactic.tactic_id)
        .outerjoin(DimConnState, FactNetworkFlow.conn_state_id == DimConnState.id)
    )
    if src_ip:
        statement = statement.where(FactNetworkFlow.src_ip == src_ip)
    if dst_port is not None:
        statement = statement.where(FactNetworkFlow.dst_port == dst_port)
    if protocol:
        statement = statement.where(DimProtocol.name == protocol.lower())
    if only_anomalies:
        statement = statement.where(FactNetworkFlow.is_anomaly.is_(True))
    statement = statement.order_by(FactNetworkFlow.ts.desc()).limit(limit)
    async with request.app.state.session_factory() as session:
        rows = (await session.execute(statement)).all()
    flows = [_serialize_flow(row) for row in rows]
    return {"total": len(flows), "flows": flows}


def _serialize_flow(row: Row) -> dict:
    fact = row[0]
    return {
        "ts": fact.ts.isoformat(),
        "src_ip": fact.src_ip,
        "src_port": fact.src_port,
        "dst_ip": fact.dst_ip,
        "dst_port": fact.dst_port,
        "protocol": row.protocol_name,
        "conn_state": row.conn_state_name,
        "iat_ms": fact.iat_ms,
        "orig_bytes": fact.orig_bytes,
        "resp_bytes": fact.resp_bytes,
        "duration": fact.duration,
        "anomaly_score": fact.anomaly_score,
        "is_anomaly": fact.is_anomaly,
        "mitre_tactic": row.mitre_id,
    }


@app.post("/api/v1/ingest/trigger")
async def trigger_ingestion(
    request: Request,
    _auth: Annotated[dict, Depends(require_role("admin", "analyst"))],
) -> dict:
    try:
        new_flows = await _run_ingestion(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ingestion failed: {exc}",
        ) from exc
    message = {"type": "ingest_complete", "new_flows": new_flows, "status": "ok"}
    await manager.broadcast(message)
    return message


async def _run_ingestion(request: Request) -> int:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        before = (
            await session.scalar(select(func.count()).select_from(FactNetworkFlow)) or 0
        )
    log_file = Path(os.getenv(LOG_FILE_ENV, DEFAULT_LOG_FILE))
    use_case = FlowNormalizerUseCase(
        source=ZeekTelemetrySource(log_file),
        repository=PostgresFlowRepository(session_factory),
    )
    await use_case.execute()
    async with session_factory() as session:
        after = (
            await session.scalar(select(func.count()).select_from(FactNetworkFlow)) or 0
        )
    return after - before


@app.patch("/api/v1/config/threshold")
async def update_threshold(
    payload: ThresholdUpdate,
    request: Request,
    _auth: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    request.app.state.epsilon_threshold = payload.epsilon_threshold
    return {"epsilon_threshold": payload.epsilon_threshold}


@app.websocket("/ws/alerts")
async def alerts_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
