import httpx
import pytest

from cascade.ais import normalize_position
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
    assert status.json()["available"] is False
    assert stream.status_code == 503


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
