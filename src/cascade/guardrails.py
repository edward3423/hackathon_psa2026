"""Request guardrails: opt-in shared-secret auth and per-client rate limiting.

The demo binds to loopback and works with none of this. These are the controls
that make the same process safe to show over a LAN or a tunnel: without them,
anyone who can reach port 8620 can reset the store mid-presentation or burn
the live-model quota with a loop of POSTs. Only POST requests are guarded -
every mutation in the API is a POST, and reads plus SSE streams stay free so
an open dashboard never trips a limit.

Configuration, all via environment variables so the local demo, the test
suites, and the guided tour need no changes:

- ``CASCADE_API_TOKEN``: when set, every POST must carry the same value in an
  ``X-Cascade-Token`` header. Unset (the default) disables the check.
- ``CASCADE_RATE_LIMIT_BURST`` (default 30): token-bucket capacity per client.
  Zero or negative disables rate limiting.
- ``CASCADE_RATE_LIMIT_PER_SECOND`` (default 1): bucket refill rate.
"""

import os
import secrets
import time
from collections.abc import Callable

from fastapi import HTTPException, Request

RATE_LIMIT_BURST_DEFAULT = 30.0
RATE_LIMIT_REFILL_DEFAULT = 1.0

TOKEN_HEADER = "x-cascade-token"

# Above this many tracked clients, stale buckets are pruned on the next take.
# Purely a bound on the limiter's own memory; never reached on loopback.
_PRUNE_THRESHOLD = 1024


class TokenBucket:
    """Per-client token buckets: ``capacity`` requests at burst, then ``refill_per_second``."""

    def __init__(
        self,
        capacity: float,
        refill_per_second: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last seen)

    def allow(self, key: str) -> bool:
        now = self.clock()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
        allowed = tokens >= 1.0
        self._buckets[key] = (tokens - 1.0 if allowed else tokens, now)
        if len(self._buckets) > _PRUNE_THRESHOLD:
            self._prune(now)
        return allowed

    def _prune(self, now: float) -> None:
        # A bucket idle long enough to be full again carries no information.
        if self.refill_per_second <= 0:
            return
        idle_horizon = self.capacity / self.refill_per_second
        self._buckets = {
            key: state for key, state in self._buckets.items() if now - state[1] < idle_horizon
        }


# Built lazily on the first guarded request rather than at import, because the
# API module calls load_dotenv() after its imports; building here would read
# the environment before .env is applied.
_limiter: TokenBucket | None = None
_limiter_built = False


def _get_limiter() -> TokenBucket | None:
    global _limiter, _limiter_built
    if not _limiter_built:
        burst = float(os.environ.get("CASCADE_RATE_LIMIT_BURST", RATE_LIMIT_BURST_DEFAULT))
        refill = float(os.environ.get("CASCADE_RATE_LIMIT_PER_SECOND", RATE_LIMIT_REFILL_DEFAULT))
        _limiter = TokenBucket(burst, refill) if burst > 0 else None
        _limiter_built = True
    return _limiter


async def guard_mutations(request: Request) -> None:
    """App-wide dependency: authenticate and rate-limit every POST."""
    if request.method != "POST":
        return

    expected = os.environ.get("CASCADE_API_TOKEN")
    if expected:
        provided = request.headers.get(TOKEN_HEADER, "")
        if not secrets.compare_digest(provided.encode(), expected.encode()):
            raise HTTPException(
                status_code=401,
                detail="This deployment requires a valid X-Cascade-Token header.",
            )

    limiter = _get_limiter()
    if limiter is not None:
        client = request.client.host if request.client else "local"
        if not limiter.allow(client):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. The demo API rate-limits mutations per client.",
            )
