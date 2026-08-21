"""Server-side AISStream adapter.

The API key stays on the server. Browser clients receive only normalized,
browser-safe vessel positions for the demo's operational areas.
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any, TypeGuard

from websockets.asyncio.client import connect

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"
DEFAULT_BOUNDING_BOXES = [
    [[10.0, 30.0], [30.0, 45.0]],  # Red Sea and Suez approaches
    [[-2.0, 100.0], [8.0, 108.0]],  # Singapore Strait approaches
]


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _validate_bounding_boxes(value: object) -> list[list[list[float]]]:
    if not isinstance(value, list) or not value:
        raise ValueError("AISSTREAM_BOUNDING_BOXES_JSON must be a non-empty JSON list")

    boxes: list[list[list[float]]] = []
    for box in value:
        if not isinstance(box, list) or len(box) != 2:
            raise ValueError("each AISStream bounding box must contain two coordinate pairs")
        coordinates: list[list[float]] = []
        for point in box:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or not all(_is_number(coordinate) for coordinate in point)
            ):
                raise ValueError("each AISStream coordinate must be [latitude, longitude]")
            latitude, longitude = (float(point[0]), float(point[1]))
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("AISStream coordinates are outside latitude/longitude limits")
            coordinates.append([latitude, longitude])
        if coordinates[0][0] >= coordinates[1][0] or coordinates[0][1] >= coordinates[1][1]:
            raise ValueError("AISStream bounding boxes must run southwest to northeast")
        boxes.append(coordinates)
    return boxes


def configured_bounding_boxes() -> list[list[list[float]]]:
    raw = os.environ.get("AISSTREAM_BOUNDING_BOXES_JSON")
    if raw is None or raw == "":
        return _validate_bounding_boxes(DEFAULT_BOUNDING_BOXES)
    return _validate_bounding_boxes(json.loads(raw))


def normalize_position(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("MessageType") != "PositionReport":
        return None
    metadata = message.get("MetaData") or {}
    report = (message.get("Message") or {}).get("PositionReport") or {}
    latitude = metadata.get("latitude", metadata.get("Latitude"))
    longitude = metadata.get("longitude", metadata.get("Longitude"))
    if not _is_number(latitude) or not _is_number(longitude):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    name = str(metadata.get("ShipName") or "").strip() or "Unidentified vessel"
    return {
        "mmsi": str(metadata.get("MMSI", "unknown")),
        "name": name,
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
            message = json.loads(raw)
            if not isinstance(message, dict):
                continue
            position = normalize_position(message)
            if position is not None:
                yield position
