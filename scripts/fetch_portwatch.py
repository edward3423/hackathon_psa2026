"""Refresh the committed IMF PortWatch snapshot for the Port of Singapore.

    uv run python scripts/fetch_portwatch.py [--start-year 2022] [--end-year 2024]

This is a maintenance tool only. It is the ONLY thing in the repository that
touches the network for crisis data, and it is never imported or invoked by
tests, CI, the API, or any runtime code path. Everything downstream reads the
committed CSV at data/raw/portwatch_singapore.csv, or the fixtures built from
it.

Source
------
IMF PortWatch (portwatch.imf.org), a joint IMF and University of Oxford
project. Daily port activity is published as an ArcGIS feature service:

    https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services
        /Daily_Ports_Data/FeatureServer/0

Endpoint quirks discovered while writing this script, all worked around below:

- String equality in a `where` clause (`ISO3='SGP'`) is rejected with HTTP 400
  "Invalid query parameters", or simply hangs. The `IN` form (`ISO3 IN
  ('SGP')`) is accepted and returns the same rows, so every string predicate
  here is written as `IN`.
- `orderByFields` on a string column (`portid`) is likewise rejected with HTTP
  400. Ordering by `date` is accepted, so pagination orders by date only.
- The service is shared and throttled. It intermittently answers with
  `{"error": {"code": 429, ...}}` ("API calls quota exceeded"), with
  `{"error": {"code": 499, "message": "Token Required"}}`, or with no answer
  at all until the socket times out. All three are transient; the retry
  wrapper below waits and tries again rather than failing the run.
- `maxRecordCount` is 1000, so day rows are paginated with `resultOffset` /
  `resultRecordCount` and a stable `orderByFields`.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "raw" / "portwatch_singapore.csv"

SERVICE_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
    "/Daily_Ports_Data/FeatureServer/0/query"
)

PORT_NAME = "Singapore"

PAGE_SIZE = 1000
MAX_ATTEMPTS = 8
QUOTA_BACKOFF_SECONDS = 60.0
TRANSIENT_BACKOFF_SECONDS = 20.0
REQUEST_TIMEOUT_SECONDS = 120.0
POLITE_PAUSE_SECONDS = 3.0

# Columns kept in the committed snapshot, in this order.
CSV_COLUMNS = [
    "date",
    "year",
    "month",
    "day",
    "portid",
    "portname",
    "country",
    "ISO3",
    "portcalls_container",
    "portcalls_cargo",
    "portcalls",
    "import_container",
    "export_container",
]

# Codes the service returns when it is busy rather than when we asked wrongly.
QUOTA_ERROR_CODES = frozenset({429, 499})


class PortWatchError(RuntimeError):
    """The endpoint refused a query in a way retrying will not fix."""


def _get(params: dict[str, str]) -> dict[str, Any]:
    """One query, retried patiently through throttling and socket timeouts."""
    url = f"{SERVICE_URL}?{urllib.parse.urlencode(params)}"
    last_detail = "no attempt made"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            last_detail = f"{type(error).__name__}: {error}"
            print(f"  attempt {attempt}/{MAX_ATTEMPTS} transport failure: {last_detail}")
            time.sleep(TRANSIENT_BACKOFF_SECONDS)
            continue

        error_body = payload.get("error")
        if error_body is None:
            return payload

        code = int(error_body.get("code", 0))
        last_detail = f"code {code}: {error_body.get('message', '')!r}"
        if code in QUOTA_ERROR_CODES:
            print(f"  attempt {attempt}/{MAX_ATTEMPTS} throttled ({last_detail}); waiting")
            time.sleep(QUOTA_BACKOFF_SECONDS)
            continue
        raise PortWatchError(f"query rejected ({last_detail}) for {url}")

    raise PortWatchError(f"gave up after {MAX_ATTEMPTS} attempts ({last_detail}) for {url}")


def _features(payload: dict[str, Any]) -> list[dict[str, Any]]:
    features = payload.get("features", [])
    return [dict(feature.get("attributes", {})) for feature in features]


def discover_port_id(probe_year: int) -> tuple[str, str]:
    """Find the Port of Singapore's portid. Returns (portid, portname).

    The dataset carries several Singaporean ports (Serangoon Harbor and an
    offshore oil terminal alongside the container port), so the probe pulls
    one day's rows for ISO3 SGP - which yields exactly one row per port - and
    then requires an exact `portname` match rather than guessing.
    """
    payload = _get(
        {
            "where": f"ISO3 IN ('SGP') AND year = {probe_year} AND month = 1 AND day = 1",
            "outFields": "portid,portname,country,ISO3",
            "returnGeometry": "false",
            "resultRecordCount": str(PAGE_SIZE),
            "f": "json",
        }
    )
    candidates = sorted(
        (str(row["portid"]), str(row["portname"]))
        for row in _features(payload)
        if row.get("portid") and row.get("portname")
    )
    if not candidates:
        raise PortWatchError("no SGP rows returned; cannot determine the Singapore portid")
    matches = [pair for pair in candidates if pair[1].strip().lower() == PORT_NAME.lower()]
    if len(matches) != 1:
        raise PortWatchError(
            f"expected exactly one port named {PORT_NAME!r}; SGP ports found: {candidates}"
        )
    chosen = matches[0]
    others = [pair for pair in candidates if pair != chosen]
    print(f"resolved portid={chosen[0]} portname={chosen[1]!r}")
    if others:
        print(f"  other SGP ports in the dataset (not fetched): {others}")
    return chosen


def fetch_rows(port_id: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
    """All daily rows for one port across an inclusive year range."""
    where = f"portid IN ('{port_id}') AND year >= {start_year} AND year <= {end_year}"
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        payload = _get(
            {
                "where": where,
                "outFields": ",".join(CSV_COLUMNS),
                "returnGeometry": "false",
                "orderByFields": "date",
                "resultOffset": str(offset),
                "resultRecordCount": str(PAGE_SIZE),
                "f": "json",
            }
        )
        page = _features(payload)
        rows.extend(page)
        print(f"  fetched {len(page)} rows at offset {offset} (total {len(rows)})")
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE
        time.sleep(POLITE_PAUSE_SECONDS)


def _iso_date(row: dict[str, Any]) -> str:
    """PortWatch date fields arrive as epoch milliseconds or as ISO strings."""
    raw = row["date"]
    if isinstance(raw, int | float):
        stamp = time.gmtime(float(raw) / 1000.0)
        return time.strftime("%Y-%m-%d", stamp)
    return str(raw)[:10]


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    ordered = sorted(rows, key=_iso_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in ordered:
            writer.writerow(
                {column: row.get(column, "") for column in CSV_COLUMNS} | {"date": _iso_date(row)}
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2024)
    args = parser.parse_args()

    port_id, _ = discover_port_id(args.start_year)
    rows = fetch_rows(port_id, args.start_year, args.end_year)
    if not rows:
        raise PortWatchError("no rows returned for Singapore; refusing to overwrite the snapshot")
    write_csv(rows, OUTPUT_PATH)
    dates = sorted(_iso_date(row) for row in rows)
    print(f"wrote {OUTPUT_PATH} ({len(rows)} rows, {dates[0]} to {dates[-1]})")


if __name__ == "__main__":
    main()
