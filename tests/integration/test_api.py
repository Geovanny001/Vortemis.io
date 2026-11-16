from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vortemis.config import ApiSettings
from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp
from vortemis.entrypoints.api import create_app
from vortemis.entrypoints.container import (
    build_session_service,
    build_telemetry_service,
)
from vortemis.infrastructure.persistence.auth import seed_default_operators
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.login_limiter import LoginLimiter
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)

_MODEL_PATH = Path("models/vortemis_ae.pt").resolve()
_CORS_ORIGIN = "https://console.example.com"
_BASE_EPOCH = 1_700_000_000.0


def _flow(
    offset: float,
    dst_port: int,
    probability: float,
    tactic: str | None,
) -> NetworkFlow:
    return NetworkFlow(
        src_ip=IPAddress("192.168.1.10"),
        dst_ip=IPAddress("10.0.0.5"),
        src_port=Port(50000),
        dst_port=Port(dst_port),
        proto=Protocol.TCP,
        ts=Timestamp.from_epoch(_BASE_EPOCH + offset),
        orig_bytes=1000,
        resp_bytes=200,
        duration=0.5,
        conn_state="SF",
        anomaly_probability=probability,
        mitre_tactic=tactic,
    )


@pytest.fixture
async def database(tmp_path: Path) -> AsyncIterator[SqlDatabase]:
    database = SqlDatabase(
        f"sqlite+aiosqlite:///{(tmp_path / 'api.db').as_posix()}",
        pooling=False,
    )
    await database.create_schema()
    await PostgresFlowRepository(database.session_factory).save_batch(
        [
            _flow(0, 445, 0.90, "TA0008"),
            _flow(100, 443, 0.90, "TA0010"),
            _flow(200, 22, 0.10, None),
        ]
    )
    async with database.session() as session:
        await seed_default_operators(session)
        await session.commit()
    yield database
    await database.dispose()


@pytest.fixture
def app(database: SqlDatabase) -> FastAPI:
    settings = ApiSettings(
        cors_origins=(_CORS_ORIGIN,),
        token_ttl=timedelta(hours=1),
    )
    return create_app(
        read_service=build_telemetry_service(database, _MODEL_PATH),
        session_service=build_session_service(database, settings.token_ttl),
        database=database,
        settings=settings,
        limiter=LoginLimiter(),
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client


async def _login(
    client: AsyncClient,
    username: str = "admin_carles",
    password: str = "VortemisAdmin2026!",
) -> str:
    response = await client.post(
        "/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_health_is_public(client: AsyncClient) -> None:
    response = await client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_login_rejects_invalid_credentials(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/login",
        json={"username": "admin_carles", "password": "wrong"},
    )

    assert response.status_code == 401


async def test_login_returns_a_token_and_identity(client: AsyncClient) -> None:
    token = await _login(client)

    response = await client.get("/v1/auth/me", headers=_auth(token))

    assert response.status_code == 200
    assert response.json() == {"username": "admin_carles", "role": "admin"}


async def test_flows_require_a_token(client: AsyncClient) -> None:
    response = await client.get("/v1/flows")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_flows_return_filters_and_pagination(
    client: AsyncClient,
) -> None:
    token = await _login(client)

    first = await client.get(
        "/v1/flows", params={"limit": 2}, headers=_auth(token)
    )
    payload = first.json()
    second = await client.get(
        "/v1/flows",
        params={"limit": 2, "cursor": payload["next_cursor"]},
        headers=_auth(token),
    )
    filtered = await client.get(
        "/v1/flows", params={"tactic": "TA0010"}, headers=_auth(token)
    )

    assert first.status_code == 200
    assert [record["dst_port"] for record in payload["records"]] == [22, 443]
    assert payload["next_cursor"]
    assert [record["dst_port"] for record in second.json()["records"]] == [445]
    assert second.json()["next_cursor"] is None
    assert [record["dst_port"] for record in filtered.json()["records"]] == [443]


async def test_summary_and_tactics(client: AsyncClient) -> None:
    token = await _login(client)

    response = await client.get("/v1/stats/summary", headers=_auth(token))

    body = response.json()
    assert body["total_flows"] == 3
    assert body["anomalies"] == 2
    assert body["by_tactic"] == {"TA0008": 1, "TA0010": 1}


async def test_top_sources_and_timeline(client: AsyncClient) -> None:
    token = await _login(client)

    sources = await client.get(
        "/v1/stats/top-sources", headers=_auth(token)
    )
    timeline = await client.get(
        "/v1/stats/timeline",
        params={"bucket_seconds": 600},
        headers=_auth(token),
    )

    assert sources.json()[0]["src_ip"] == "192.168.1.10"
    assert sources.json()[0]["flows"] == 3
    assert sources.json()[0]["anomalies"] == 2
    assert len(timeline.json()) == 1
    assert timeline.json()[0]["flows"] == 3


async def test_engine_metadata(client: AsyncClient) -> None:
    token = await _login(client)

    response = await client.get("/v1/engine/metadata", headers=_auth(token))

    body = response.json()
    assert response.status_code == 200
    assert body["architecture"] == "6 -> 16 -> 3 -> 16 -> 6"
    assert body["feature_dim"] == 6
    assert len(body["mean"]) == 6


async def test_logout_revokes_the_token(client: AsyncClient) -> None:
    token = await _login(client)

    logout = await client.post("/v1/auth/logout", headers=_auth(token))
    after = await client.get("/v1/auth/me", headers=_auth(token))

    assert logout.status_code == 204
    assert after.status_code == 401


async def test_invalid_filters_return_422(client: AsyncClient) -> None:
    token = await _login(client)

    response = await client.get(
        "/v1/flows", params={"src_port": 0}, headers=_auth(token)
    )

    assert response.status_code == 422


async def test_login_is_rate_limited(client: AsyncClient) -> None:
    payload = {"username": "soc_analyst", "password": "wrong"}

    for _ in range(5):
        response = await client.post("/v1/auth/login", json=payload)
        assert response.status_code == 401

    blocked = await client.post("/v1/auth/login", json=payload)

    assert blocked.status_code == 429
    assert blocked.headers["retry-after"]


async def test_cors_allows_only_configured_origins(
    client: AsyncClient,
) -> None:
    allowed = await client.options(
        "/v1/flows",
        headers={
            "Origin": _CORS_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = await client.options(
        "/v1/flows",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers.get("access-control-allow-origin") == _CORS_ORIGIN
    assert "access-control-allow-origin" not in denied.headers


def test_openapi_documents_the_contract(app: FastAPI) -> None:
    schema = app.openapi()

    assert "/v1/flows" in schema["paths"]
    assert "/v1/auth/login" in schema["paths"]
    assert "HTTPBearer" in schema["components"]["securitySchemes"]
