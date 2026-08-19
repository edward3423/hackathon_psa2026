"""Secure AISStream WebSocket adapter for browser-safe vessel positions."""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from websockets.asyncio.client import connect

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"
DEFAULT_BOUNDING_BOXES = [
    [[10.0, 30.0], [30.0, 45.0]],
    [[-2.0, 100.0], [8.0, 108.0]],
]


def configured_bounding_boxes() -> list[list[list[float]]]:
    raw = os.environ.get("AISSTREAM_BOUNDING_BOXES_JSON")
    if raw is None:
        return DEFAULT_BOUNDING_BOXES
    parsed = json.loads(raw)
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("AISSTREAM_BOUNDING_BOXES_JSON must be a non-empty JSON list")
    return parsed


def normalize_position(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("MessageType") != "PositionReport":
        return None
    metadata = message.get("MetaData") or {}
    report = (message.get("Message") or {}).get("PositionReport") or {}
    latitude = metadata.get("latitude", metadata.get("Latitude"))
    longitude = metadata.get("longitude", metadata.get("Longitude"))
    if not isinstance(latitude, int | float) or not isinstance(longitude, int | float):
        return None
    return {
        "mmsi": str(metadata.get("MMSI", "unknown")),
        "name": str(metadata.get("ShipName") or "Unidentified vessel").strip(),
        "latitude": float(latitude),
        "longitude": float(longitude),
        "course": report.get("Cog"),
        "speed_knots": report.get("Sog"),
        "heading": report.get("TrueHeading"),
        "timestamp": metadata.get("time_utc"),
        "source": "LIVE_AIS",
    }


async def live_positions(api_key: str) -> AsyncIterator[dict[str, Any]]:
    subscription = {
        "APIKey": api_key,
        "BoundingBoxes": configured_bounding_boxes(),
        "FilterMessageTypes": ["PositionReport"],
    }
    async with connect(AISSTREAM_URL, ping_interval=20, ping_timeout=20) as websocket:
        await websocket.send(json.dumps(subscription))
        async for raw in websocket:
            if not isinstance(raw, str):
                continue
            position = normalize_position(json.loads(raw))
            if position is not None:
                yield position
