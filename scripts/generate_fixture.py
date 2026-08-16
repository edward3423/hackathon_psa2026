"""Deterministic synthetic world generator for the CASCADE golden scenario.

Running `uv run python scripts/generate_fixture.py` regenerates
fixtures/golden_world.json byte-identically. All randomness flows through
random.Random(SEED); the system clock and the global random module are never
used.

Timing model (all times UTC, golden alert from fixtures/golden_scenario.json):

- MV ATLAS STAR original ETA (Estimated Time of Arrival) is 2026-09-14T06:00Z.
- A delay of D hours shifts the ETA to 06:00 + D.
- A container is ready for its onward vessel at revised ETA + handling_hours.
- Connection margin = onward connection_cutoff - ready time.
- Classification: SAFE when margin > 4h, AT_RISK when 0 <= margin <= 4h,
  MISSED when margin < 0h.

Cutoffs are expressed below as offsets from the original ETA so the margin at
delay D is simply offset - handling_hours - D:

- MV MERIDIAN WAVE  cutoff +22h: mostly SAFE at 6h, mostly MISSED at 18h.
- MV CORAL EMPRESS  cutoff +30h: SAFE at 6h, full SAFE/AT_RISK/MISSED mix
  at 18h, mostly MISSED at 24h.
- MV PACIFIC HARRIER cutoff +34h: SAFE at 6h, SAFE with an AT_RISK tail at
  18h, full mix at 24h.
- MV JADE HORIZON (+60h) and MV AURORA BREEZE (+78h) stay SAFE at any
  supported delay; they are the two unaffected vessels.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cascade.contracts import (
    AlternativeSailing,
    CargoType,
    Container,
    CostRates,
    Vessel,
    VesselRole,
    WorldFixture,
    YardBlock,
)

SEED = 42
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "fixtures" / "golden_world.json"

TERMINAL = "PSA Singapore - Synthetic Demo Terminal 1"
INBOUND_VESSEL = "MV ATLAS STAR"
ORIGINAL_ETA = datetime(2026, 9, 14, 6, 0, tzinfo=UTC)

SYNTHETIC_NOTICE = (
    "All vessels, containers, yard blocks, capacities, cutoffs, sailings, and "
    "cost rates in this fixture are synthetic and illustrative. They do not "
    "describe real PSA operations."
)

# (name, cutoff offset hours from original ETA, eta offset, etd offset)
AFFECTED_OUTBOUND = [
    ("MV MERIDIAN WAVE", 22, 14, 28),
    ("MV CORAL EMPRESS", 30, 22, 36),
    ("MV PACIFIC HARRIER", 34, 26, 40),
]
UNAFFECTED_OUTBOUND = [
    ("MV JADE HORIZON", 60, 52, 66),
    ("MV AURORA BREEZE", 78, 70, 84),
]

# Yard blocks: 44 reefer plugs in total, deliberately fewer than the 60 pharma
# reefers, so rushing every reefer into powered slots is physically impossible
# (the golden dispute). Initial occupancy leaves each block close enough to the
# 85 percent congestion line that missed connections push at least one block
# across it within the 72-hour forecast.
YARD_BLOCKS = [
    ("YB1", 480, 18, 310, 10),
    ("YB2", 500, 14, 320, 8),
    ("YB3", 460, 12, 280, 6),
    ("YB4", 520, 0, 330, 0),
]
REEFER_BLOCKS = ["YB1", "YB2", "YB3"]
ALL_BLOCKS = ["YB1", "YB2", "YB3", "YB4"]

# (cargo_type, onward vessel or None for import cargo, count)
CONTAINER_SPEC = [
    (CargoType.PHARMA_REEFER, "MV MERIDIAN WAVE", 20),
    (CargoType.PHARMA_REEFER, "MV CORAL EMPRESS", 20),
    (CargoType.PHARMA_REEFER, "MV PACIFIC HARRIER", 20),
    (CargoType.TIME_CRITICAL_MANUFACTURING, "MV MERIDIAN WAVE", 40),
    (CargoType.TIME_CRITICAL_MANUFACTURING, "MV CORAL EMPRESS", 40),
    (CargoType.TIME_CRITICAL_MANUFACTURING, "MV PACIFIC HARRIER", 30),
    (CargoType.TIME_CRITICAL_MANUFACTURING, "MV JADE HORIZON", 10),
    (CargoType.TIME_CRITICAL_MANUFACTURING, "MV AURORA BREEZE", 10),
    (CargoType.GENERAL_DRY, "MV MERIDIAN WAVE", 45),
    (CargoType.GENERAL_DRY, "MV CORAL EMPRESS", 45),
    (CargoType.GENERAL_DRY, "MV PACIFIC HARRIER", 40),
    (CargoType.GENERAL_DRY, "MV JADE HORIZON", 20),
    (CargoType.GENERAL_DRY, "MV AURORA BREEZE", 20),
    (CargoType.GENERAL_DRY, None, 40),
]

# (name, replaced vessel, departs offset hours, cutoff offset hours, capacity)
ALTERNATIVE_SAILINGS = [
    ("MV NOVA CREST", "MV MERIDIAN WAVE", 62, 56, 70),
    ("MV DELTA CROWN", "MV MERIDIAN WAVE", 98, 92, 40),
    ("MV BALTIC SPRING", "MV CORAL EMPRESS", 72, 66, 60),
    ("MV SUNDA STRAIT", "MV PACIFIC HARRIER", 86, 80, 55),
]

# Documented illustrative round numbers, in synthetic dollars.
COST_RATES = CostRates(
    dwell_per_container_hour=4.0,
    reefer_risk_per_hour=25.0,
    missed_connection_penalty=1200.0,
    crane_hour=600.0,
    rebooking_fee=350.0,
)


def _offset(hours: int) -> datetime:
    return ORIGINAL_ETA + timedelta(hours=hours)


def _build_vessels() -> list[Vessel]:
    vessels = [
        Vessel(
            name=INBOUND_VESSEL,
            role=VesselRole.INBOUND,
            port_call="SGSIN-PSA-2042",
            eta=ORIGINAL_ETA,
            etd=_offset(16),
            connection_cutoff=None,
        )
    ]
    for index, (name, cutoff, eta, etd) in enumerate(AFFECTED_OUTBOUND + UNAFFECTED_OUTBOUND):
        vessels.append(
            Vessel(
                name=name,
                role=VesselRole.OUTBOUND,
                port_call=f"SGSIN-PSA-{2043 + index}",
                eta=_offset(eta),
                etd=_offset(etd),
                connection_cutoff=_offset(cutoff),
            )
        )
    return vessels


def _build_yard_blocks() -> list[YardBlock]:
    return [
        YardBlock(
            block_id=block_id,
            container_capacity=capacity,
            reefer_plugs=plugs,
            initial_containers=initial,
            initial_reefers_on_power=on_power,
        )
        for block_id, capacity, plugs, initial, on_power in YARD_BLOCKS
    ]


def _build_containers(rng: random.Random) -> list[Container]:
    containers: list[Container] = []
    serial = 1
    for cargo_type, onward_vessel, count in CONTAINER_SPEC:
        for _ in range(count):
            is_reefer = cargo_type is CargoType.PHARMA_REEFER
            containers.append(
                Container(
                    container_id=f"CASU{serial:07d}",
                    cargo_type=cargo_type,
                    requires_power=is_reefer,
                    inbound_vessel=INBOUND_VESSEL,
                    onward_vessel=onward_vessel,
                    yard_block=rng.choice(REEFER_BLOCKS if is_reefer else ALL_BLOCKS),
                    # Reefers get priority handling (3-8h); other cargo takes
                    # 3-14h. Spread against the cutoff offsets, this yields a
                    # believable SAFE / AT_RISK / MISSED mix at 18h and
                    # sensibly different mixes at 6h and 24h.
                    handling_hours=float(rng.randint(3, 8) if is_reefer else rng.randint(3, 14)),
                )
            )
            serial += 1
    return containers


def _build_alternative_sailings() -> list[AlternativeSailing]:
    return [
        AlternativeSailing(
            vessel_name=name,
            replaces_onward_vessel=replaces,
            departs=_offset(departs),
            connection_cutoff=_offset(cutoff),
            available_capacity=capacity,
        )
        for name, replaces, departs, cutoff, capacity in ALTERNATIVE_SAILINGS
    ]


def build_world() -> WorldFixture:
    rng = random.Random(SEED)
    return WorldFixture(
        seed=SEED,
        terminal=TERMINAL,
        vessels=_build_vessels(),
        yard_blocks=_build_yard_blocks(),
        containers=_build_containers(rng),
        alternative_sailings=_build_alternative_sailings(),
        cost_rates=COST_RATES,
        synthetic_notice=SYNTHETIC_NOTICE,
    )


def render_world_json(world: WorldFixture) -> str:
    return json.dumps(world.model_dump(mode="json"), indent=2) + "\n"


def main() -> None:
    world = build_world()
    OUTPUT_PATH.write_text(render_world_json(world), encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT_PATH} ({len(world.containers)} containers)")


if __name__ == "__main__":
    main()
