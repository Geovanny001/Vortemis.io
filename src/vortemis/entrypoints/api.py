from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from vortemis.application.errors import (
    InvalidQueryError,
    NotFoundError,
    PermissionDeniedError,
)
from vortemis.application.ports.driven.operator_admin import OperatorAdminPort
from vortemis.application.queries.dto import OperatorIdentity
from vortemis.application.queries.filters import FlowFilters
from vortemis.application.queries.telemetry import TelemetryReadService
from vortemis.application.sessions import OperatorSessionService
from vortemis.config import ApiSettings, Settings
from vortemis.entrypoints.api_schemas import (
    FlowPageSchema,
    HealthResponse,
    IdentityResponse,
    LoginRequest,
    ModelMetadataSchema,
    PasswordRequest,
    SourceAggregateSchema,
    SummaryResponse,
    TimelinePointSchema,
    TokenResponse,
    to_flow_page,
    to_metadata,
    to_source,
    to_timeline,
)
from vortemis.entrypoints.container import (
    build_operator_admin,
    build_session_service,
    build_telemetry_service,
)
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.login_limiter import LoginLimiter

API_VERSION = "1.0.0"
DEFAULT_THRESHOLD = 0.70
MAX_LIMIT = 500


def create_app(
    read_service: TelemetryReadService,
    session_service: OperatorSessionService,
    operator_admin: OperatorAdminPort,
    database: SqlDatabase,
    settings: ApiSettings,
    log_file: Path,
    limiter: LoginLimiter | None = None,
) -> FastAPI:
    app = FastAPI(title="Vortemis.io API", version=API_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type"],
    )
    bearer = HTTPBearer(auto_error=False)
    guard = limiter or LoginLimiter()

    @app.exception_handler(InvalidQueryError)
    async def invalid_query(
        request: Request, exc: InvalidQueryError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(PermissionDeniedError)
    async def forbidden(
        request: Request, exc: PermissionDeniedError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(SQLAlchemyError)
    async def unavailable(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "database unavailable"}
        )

    async def current_operator(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> OperatorIdentity:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        identity = await session_service.resolve(credentials.credentials)
        if identity is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return identity

    async def require_admin(
        identity: OperatorIdentity = Depends(current_operator),
    ) -> OperatorIdentity:
        if identity.role != "admin":
            raise PermissionDeniedError("admin role required")
        return identity

    def flow_filters(
        since: datetime | None = None,
        until: datetime | None = None,
        src_ip: str | None = None,
        dst_ip: str | None = None,
        src_port: int | None = None,
        dst_port: int | None = None,
        protocol: str | None = None,
        tactic: str | None = None,
        min_probability: float | None = None,
    ) -> FlowFilters:
        try:
            return FlowFilters(
                since=since,
                until=until,
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_port,
                dst_port=dst_port,
                protocol=protocol,
                tactic=tactic,
                min_probability=min_probability,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        try:
            async with database.session() as session:
                await session.scalar(text("SELECT 1"))
        except Exception:
            raise HTTPException(
                status_code=503, detail="database unavailable"
            ) from None
        return HealthResponse(status="ok", database="ok")

    @app.post("/v1/auth/login", response_model=TokenResponse)
    async def login(payload: LoginRequest) -> TokenResponse:
        if not guard.allow(payload.username):
            raise HTTPException(
                status_code=429,
                detail="too many failed attempts",
                headers={
                    "Retry-After": str(
                        int(guard.remaining_seconds(payload.username))
                    )
                },
            )
        result = await session_service.login(
            payload.username, payload.password
        )
        if result is None:
            guard.record_failure(payload.username)
            raise HTTPException(status_code=401, detail="invalid credentials")
        guard.record_success(payload.username)
        ttl = int(
            (result.token.expires_at - datetime.now(UTC)).total_seconds()
        )
        return TokenResponse(
            access_token=result.token.token,
            expires_in=max(ttl, 0),
            role=result.identity.role,
        )

    @app.post("/v1/auth/logout", status_code=204)
    async def logout(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
        identity: OperatorIdentity = Depends(current_operator),
    ) -> Response:
        if credentials is not None:
            await session_service.logout(credentials.credentials)
        return Response(status_code=204)

    @app.get("/v1/auth/me", response_model=IdentityResponse)
    async def me(
        identity: OperatorIdentity = Depends(current_operator),
    ) -> IdentityResponse:
        return IdentityResponse(
            username=identity.username, role=identity.role
        )

    @app.get("/v1/flows", response_model=FlowPageSchema)
    async def list_flows(
        filters: FlowFilters = Depends(flow_filters),
        limit: int = Query(100, ge=1, le=MAX_LIMIT),
        cursor: str | None = None,
        identity: OperatorIdentity = Depends(current_operator),
    ) -> FlowPageSchema:
        try:
            page = await read_service.search_flows(
                filters=filters, limit=limit, cursor=cursor
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return to_flow_page(page)

    @app.get("/v1/stats/summary", response_model=SummaryResponse)
    async def summary(
        filters: FlowFilters = Depends(flow_filters),
        threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0),
        identity: OperatorIdentity = Depends(current_operator),
    ) -> SummaryResponse:
        return SummaryResponse(
            total_flows=await read_service.count_flows(filters),
            anomalies=await read_service.count_anomalies(
                threshold, filters
            ),
            by_tactic=await read_service.count_by_tactic(filters),
        )

    @app.get(
        "/v1/stats/top-sources",
        response_model=list[SourceAggregateSchema],
    )
    async def top_sources(
        filters: FlowFilters = Depends(flow_filters),
        threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0),
        limit: int = Query(10, ge=1, le=100),
        identity: OperatorIdentity = Depends(current_operator),
    ) -> list[SourceAggregateSchema]:
        sources = await read_service.top_sources(
            threshold, filters, limit=limit
        )
        return [to_source(source) for source in sources]

    @app.get(
        "/v1/stats/timeline",
        response_model=list[TimelinePointSchema],
    )
    async def timeline(
        filters: FlowFilters = Depends(flow_filters),
        threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0),
        bucket_seconds: int = Query(60, ge=10, le=86400),
        identity: OperatorIdentity = Depends(current_operator),
    ) -> list[TimelinePointSchema]:
        points = await read_service.timeline(
            threshold, bucket_seconds=bucket_seconds, filters=filters
        )
        return [to_timeline(point) for point in points]

    @app.get("/v1/engine/metadata", response_model=ModelMetadataSchema)
    async def engine_metadata(
        identity: OperatorIdentity = Depends(current_operator),
    ) -> ModelMetadataSchema:
        metadata = await read_service.model_metadata()
        if metadata is None:
            raise HTTPException(
                status_code=404, detail="model checkpoint not available"
            )
        return to_metadata(metadata)

    @app.post("/v1/admin/purge", status_code=204)
    async def purge(
        identity: OperatorIdentity = Depends(require_admin),
    ) -> Response:
        await read_service.purge(log_file)
        return Response(status_code=204)

    @app.put("/v1/admin/operators/{username}/password", status_code=204)
    async def rotate_password(
        username: str,
        payload: PasswordRequest,
        identity: OperatorIdentity = Depends(require_admin),
    ) -> Response:
        await operator_admin.set_password(
            username, payload.password, payload.role
        )
        return Response(status_code=204)

    return app


def build_app() -> FastAPI:
    settings = Settings.from_env()
    api_settings = ApiSettings.from_env()
    database = SqlDatabase(settings.database_url)
    return create_app(
        read_service=build_telemetry_service(database, settings.model_path),
        session_service=build_session_service(
            database, api_settings.token_ttl
        ),
        operator_admin=build_operator_admin(database),
        database=database,
        settings=api_settings,
        log_file=settings.log_file,
    )


app = build_app()
