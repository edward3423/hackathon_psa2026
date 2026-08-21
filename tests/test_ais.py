from collections.abc import AsyncIterator

import httpx
import pytest

from cascade import api
from cascade.ais import configured_bounding_boxes, normalize_position
from cascade.api import app


@pytest.mark.anyio
async def test_ais_is_explicitly_offline_without_server_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AISSTREAM_API_KEY", raising=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        status = await client.get("/api/ais/status")
        stream = await client.get("/api/ais/stream")
    assert status.json()["available"] is False
    assert stream.status_code == 503
    assert status.json()["provider"] is None
    assert status.json()["coverage"] == "Red Sea and Singapore approaches"


def test_position_report_is_normalized() -> None:
    position = normalize_position(
        {
            "MessageType": "PositionReport",
            "MetaData": {
                "MMSI": 123456789,
                "ShipName": " TEST SHIP ",
                "latitude": 1.25,
                "longitude": 103.8,
                "time_utc": "2026-08-19T10:00:00Z",
            },
            "Message": {"PositionReport": {"Cog": 92.5, "Sog": 12.4, "TrueHeading": 90}},
        }
    )
    assert position is not None
    assert position["mmsi"] == "123456789"
    assert position["name"] == "TEST SHIP"
    assert position["speed_knots"] == 12.4
    assert position == {
        "mmsi": "123456789",
        "name": "TEST SHIP",
        "latitude": 1.25,
        "longitude": 103.8,
        "course": 92.5,
        "speed_knots": 12.4,
        "heading": 90,
        "timestamp": "2026-08-19T10:00:00Z",
        "source": "LIVE_AIS",
    }


def test_non_position_and_invalid_coordinates_are_ignored() -> None:
    assert normalize_position({"MessageType": "ShipStaticData"}) is None
    assert (
        normalize_position(
            {
                "MessageType": "PositionReport",
                "MetaData": {"latitude": True, "longitude": 103.8},
            }
        )
        is None
    )
    assert (
        normalize_position(
            {
                "MessageType": "PositionReport",
                "MetaData": {"latitude": 91, "longitude": 103.8},
            }
        )
        is None
    )


def test_custom_bounding_boxes_are_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AISSTREAM_BOUNDING_BOXES_JSON", "[[[10,30],[30,45]]]")
    assert configured_bounding_boxes() == [[[10.0, 30.0], [30.0, 45.0]]]

    monkeypatch.setenv("AISSTREAM_BOUNDING_BOXES_JSON", "[[[30,45],[10,30]]]")
    with pytest.raises(ValueError, match="southwest to northeast"):
        configured_bounding_boxes()


@pytest.mark.anyio
async def test_stream_forwards_normalized_positions_without_the_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_positions(api_key: str) -> AsyncIterator[dict[str, str]]:
        assert api_key == "server-secret"
        yield {"mmsi": "123456789", "name": "TEST SHIP"}

    monkeypatch.setattr(api, "live_positions", fake_positions)
    chunks = [chunk async for chunk in api._stream_ais("server-secret")]

    assert chunks == ['event: position\ndata: {"mmsi": "123456789", "name": "TEST SHIP"}\n\n']
    assert "server-secret" not in chunks[0]


@pytest.mark.anyio
async def test_stream_hides_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_positions(_api_key: str) -> AsyncIterator[dict[str, str]]:
        raise RuntimeError("provider leaked a secret")
        yield {}

    monkeypatch.setattr(api, "live_positions", failing_positions)
    chunks = [chunk async for chunk in api._stream_ais("server-secret")]

    assert len(chunks) == 1
    assert "provider_error" in chunks[0]
    assert "secret" not in chunks[0]
