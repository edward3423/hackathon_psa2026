# Crisis data for the Act 2 Red Sea 2024 benchmark

## Attribution

Daily port activity data is from **IMF PortWatch (portwatch.imf.org), a joint
IMF and University of Oxford project**. It is redistributed here as a small
committed snapshot so the benchmark is reproducible offline; PortWatch remains
the authority for the numbers.

Dataset page:
<https://portwatch.imf.org/datasets/959214444157458aad969389b3ebe1a0_0/about>
Methodology: <https://portwatch.imf.org/pages/data-and-methodology>

## What is committed

| Path | Contents |
|---|---|
| `data/raw/portwatch_singapore.csv` | Daily PortWatch rows for the Port of Singapore |

- Port: `portid=port1201`, `portname=Singapore`, `ISO3=SGP`. PortWatch also
  carries two other Singaporean ports - `port1182` Serangoon Harbor and
  `fso161` Singapore - Offshore Oil Terminal 1. Neither is the container port
  and neither is included.
- Date range: **2022-01-01 to 2024-12-31**, one row per day, no gaps.
- Rows: **1096** (plus one header line).
- Columns kept: `date, year, month, day, portid, portname, country, ISO3,
  portcalls_container, portcalls_cargo, portcalls, import_container,
  export_container`.
- SHA-256 of the committed file:
  `3c98059ec448461f7d288dc8e73bb8e5adf5ca260e8509daafbe8fe4e9665962`
  (also pinned in `fixtures/crisis_manifest.json`).

Sanity values from the snapshot, for anyone checking it against PortWatch:
2023 has 14,943 container port calls across 365 days (mean 40.9 per day);
2024-05-17 records 33, 2024-05-28 records 44, 2024-07-31 records 24.

## Exact query used

The ArcGIS feature service behind the dataset is

```
https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Ports_Data/FeatureServer/0/query
```

Port discovery (one probe day, so each Singaporean port appears exactly once):

```
where=ISO3 IN ('SGP') AND year = 2022 AND month = 1 AND day = 1
outFields=portid,portname,country,ISO3
returnGeometry=false&resultRecordCount=1000&f=json
```

Row download, paginated at the service's `maxRecordCount` of 1000:

```
where=portid IN ('port1201') AND year >= 2022 AND year <= 2024
outFields=date,year,month,day,portid,portname,country,ISO3,portcalls_container,
          portcalls_cargo,portcalls,import_container,export_container
returnGeometry=false&orderByFields=date&f=json
resultOffset=0,1000,...&resultRecordCount=1000
```

Two endpoint quirks are worked around in the fetch script and are worth knowing
before hand-crafting a query:

- String **equality** in a `where` clause (`ISO3='SGP'`) is rejected with HTTP
  400 "Invalid query parameters" or hangs until the socket times out. The `IN`
  form is accepted and returns the same rows.
- `orderByFields` on a string column (for example `portid`) is also rejected
  with HTTP 400. Ordering by `date` works.

The service is shared and throttled: it intermittently returns
`{"error": {"code": 429, ...}}` ("API calls quota exceeded"),
`{"error": {"code": 499, "message": "Token Required"}}`, or nothing at all.
All three are transient and the fetch script retries through them.

## Refreshing the snapshot

```
uv run python scripts/fetch_portwatch.py [--start-year 2022] [--end-year 2024]
uv run python scripts/build_crisis_fixture.py
```

`scripts/fetch_portwatch.py` is the only thing in this repository that touches
the network for crisis data. It is never imported or invoked by tests, CI, the
API, or any runtime code path - runtime reads only the validated fixtures under
`fixtures/`, exactly as it does for `golden_world.json`.

After refreshing, update the SHA-256 above (`fixtures/crisis_manifest.json`
carries the machine-readable copy) and re-run
`uv run pytest tests/test_fixture_crisis.py`, which asserts that the fixtures
regenerate byte-identically and that the manifest matches what is on disk.

## Ground truth

`data/ground_truth_redsea_2024.json` holds the hand-curated published scalars
for the 2024 Red Sea crisis at Singapore, each with its value, unit, source,
source date and URL. It is the human-editable copy; the machine-read copy is
`fixtures/crisis_ground_truth.json`, which `scripts/build_crisis_fixture.py`
emits together with the reconstructed daily wait curve. Every anchor is
`RECORDED` - copied unchanged from the named publication. The wait curve is
`RECONSTRUCTED` and is not a measurement; its derivation is spelled out in the
fixture's own `historical_curve_method` field.
