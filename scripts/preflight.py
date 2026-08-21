"""CASCADE demo preflight check.

Run from the repository root:

    uv run python scripts/preflight.py [--live]

Checks, in order:
  1. Ports 8620 and 5620 are free or occupied by our own services.
  2. Repository fixtures parse against the shared contracts, and every input
     the crisis manifest names still hashes to what it recorded.
  3. GEMINI_API_KEY presence in .env (warning only).
  4. With --live and a key present: one cheap Gemini generate call.

Exit code is nonzero when any hard check fails. Warnings never fail the run.
"""

import argparse
import hashlib
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import TypeAdapter, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cascade.contracts import (  # noqa: E402
    ArrivalStreamFixture,
    BenchmarkResult,
    FixtureManifest,
    GroundTruthFixture,
    ScenarioState,
    TraceEvent,
    WorldFixture,
)

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"

BACKEND_PORT = 8620
FRONTEND_PORT = 5620
GEMINI_TOKEN = "CASCADE_GEMINI_OK"
DEFAULT_MODEL = "gemini-3.5-flash"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str

    @property
    def hard_failure(self) -> bool:
        return self.status == FAIL


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _http_get(url: str, timeout: float = 3.0) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body: bytes = response.read(65536)
            return body.decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def check_backend_port() -> CheckResult:
    name = f"port {BACKEND_PORT} (backend)"
    if not _port_open(BACKEND_PORT):
        return CheckResult(name, PASS, "free")
    body = _http_get(f"http://127.0.0.1:{BACKEND_PORT}/api/health")
    if body is not None and '"status"' in body and '"ok"' in body:
        return CheckResult(name, PASS, "occupied by the CASCADE API (healthy)")
    return CheckResult(name, FAIL, "occupied by an unknown service; stop it or change ports")


def check_frontend_port() -> CheckResult:
    name = f"port {FRONTEND_PORT} (frontend)"
    if not _port_open(FRONTEND_PORT):
        return CheckResult(name, PASS, "free")
    body = _http_get(f"http://127.0.0.1:{FRONTEND_PORT}/")
    if body is not None and "CASCADE" in body:
        return CheckResult(name, PASS, "occupied by the CASCADE frontend dev server")
    return CheckResult(name, FAIL, "occupied by an unknown service; stop it or change ports")


def _validate_fixture(path: Path, adapter: TypeAdapter[Any] | None, required: bool) -> CheckResult:
    name = f"fixture {path.relative_to(REPO_ROOT).as_posix()}"
    if not path.exists():
        if required:
            return CheckResult(name, FAIL, "missing")
        return CheckResult(name, WARN, "absent; skipped (expected from another workstream)")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return CheckResult(name, FAIL, f"invalid JSON: {error}")
    if adapter is None:
        return CheckResult(name, PASS, "valid JSON (no contract model bound)")
    try:
        adapter.validate_python(data)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        return CheckResult(name, FAIL, f"contract violation at {location}: {first['msg']}")
    return CheckResult(name, PASS, "parses against contracts")


def check_manifest_hashes() -> CheckResult:
    """Every input the manifest names must still hash to what it recorded.

    The manifest is what a ``BenchmarkResult`` carries to say which data
    produced it, so a stale entry is worse than a missing one: the result would
    claim provenance it does not have. Hashing the bytes on disk is the only
    way to tell, and it is cheap enough to do on every preflight.
    """
    name = "crisis fixture manifest hashes"
    path = REPO_ROOT / "fixtures" / "crisis_manifest.json"
    if not path.exists():
        return CheckResult(name, FAIL, "fixtures/crisis_manifest.json is missing")
    try:
        manifest = FixtureManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, OSError, UnicodeDecodeError) as error:
        return CheckResult(name, FAIL, f"unreadable manifest: {error}")

    missing: list[str] = []
    stale: list[str] = []
    for relative, expected in sorted(manifest.hashes.items()):
        target = REPO_ROOT / relative
        if not target.exists():
            missing.append(relative)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            stale.append(relative)
    if missing or stale:
        parts = [f"missing {', '.join(missing)}"] if missing else []
        if stale:
            parts.append(f"changed since the manifest was written: {', '.join(stale)}")
        return CheckResult(
            name,
            FAIL,
            f"{'; '.join(parts)}; re-run scripts/build_crisis_fixture.py",
        )
    return CheckResult(name, PASS, f"{len(manifest.hashes)} input(s) match")


def check_fixtures() -> list[CheckResult]:
    fixtures_dir = REPO_ROOT / "fixtures"
    trace_list = TypeAdapter(list[TraceEvent])
    plan: list[tuple[str, TypeAdapter[Any] | None, bool]] = [
        ("golden_scenario.json", TypeAdapter(ScenarioState), True),
        ("fake_agent_events.json", trace_list, True),
        ("replay_events.json", trace_list, True),
        ("golden_world.json", TypeAdapter(WorldFixture), False),
        ("evidence_pack.json", None, False),
        # Act 2 crisis benchmark. Required: the benchmark, its API surface and
        # its golden all read these, and a demo missing them fails loudly
        # rather than quietly running Act 1 only.
        ("crisis_arrivals.json", TypeAdapter(ArrivalStreamFixture), True),
        ("crisis_ground_truth.json", TypeAdapter(GroundTruthFixture), True),
        ("crisis_manifest.json", TypeAdapter(FixtureManifest), True),
        # The pinned seed-42 benchmark. Validating it here catches a golden
        # written by an older contract before a test has to.
        ("benchmark_golden.json", TypeAdapter(BenchmarkResult), True),
    ]
    results = [
        _validate_fixture(fixtures_dir / filename, adapter, required)
        for filename, adapter, required in plan
    ]
    results.append(check_manifest_hashes())
    return results


def _load_env_key() -> str | None:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path, override=False)
        except ImportError:
            pass
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def check_gemini_key(api_key: str | None) -> CheckResult:
    name = "GEMINI_API_KEY in .env"
    if api_key:
        return CheckResult(name, PASS, "configured")
    return CheckResult(name, WARN, "not configured; live Gemini runs will be unavailable")


def check_gemini_live(api_key: str | None, live: bool) -> CheckResult:
    name = "gemini live reachability"
    if not live:
        return CheckResult(name, SKIP, "pass --live to run the live model check")
    if not api_key:
        return CheckResult(name, SKIP, "no API key configured; nothing to test")

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    started = perf_counter()
    try:
        from google import genai
        from google.genai import types
    except ImportError as error:
        return CheckResult(name, FAIL, f"google-genai SDK unavailable: {error}")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=60_000,
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=1,
                max_delay=4,
                http_status_codes=[408, 429, 500, 502, 503, 504],
            ),
        ),
    )
    try:
        response = client.models.generate_content(
            model=model,
            contents=f"Reply with exactly this token and nothing else: {GEMINI_TOKEN}",
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=64,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = (response.text or "").strip()
    except Exception as error:  # SDK raises transport-specific errors.
        safe = str(error).replace(api_key, "[REDACTED]")
        return CheckResult(name, FAIL, f"{type(error).__name__}: {safe}")
    finally:
        client.close()

    elapsed_ms = round((perf_counter() - started) * 1000)
    if text != GEMINI_TOKEN:
        return CheckResult(name, FAIL, f"model responded but token mismatch: {text!r}")
    return CheckResult(name, PASS, f"model={model} latency_ms={elapsed_ms}")


def main() -> int:
    parser = argparse.ArgumentParser(description="CASCADE demo preflight check.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also verify Gemini model reachability with one cheap generate call.",
    )
    args = parser.parse_args()

    results: list[CheckResult] = [check_backend_port(), check_frontend_port()]
    results.extend(check_fixtures())
    api_key = _load_env_key()
    results.append(check_gemini_key(api_key))
    results.append(check_gemini_live(api_key, args.live))

    width = max(len(result.name) for result in results)
    print("CASCADE preflight")
    print("-" * (width + 12))
    for result in results:
        print(f"{result.status:<5} {result.name:<{width}}  {result.detail}")
    print("-" * (width + 12))

    failures = [result for result in results if result.hard_failure]
    warnings = [result for result in results if result.status == WARN]
    if failures:
        print(f"RESULT: FAIL ({len(failures)} hard failure(s), {len(warnings)} warning(s))")
        return 1
    print(f"RESULT: PASS ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
