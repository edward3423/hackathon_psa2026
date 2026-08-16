"""Hand-written world fixture builders for engine unit tests.

Small, deterministic worlds independent of the golden fixture that another
agent generates in parallel.
"""

from datetime import datetime, timedelta

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

BASE = datetime(2026, 1, 1, 0, 0)
REVISED_ETA = BASE + timedelta(hours=18)


def make_container(
    container_id: str,
    cargo_type: CargoType = CargoType.GENERAL_DRY,
    requires_power: bool = False,
    onward_vessel: str | None = "MV OUT",
    yard_block: str = "B1",
    handling_hours: float = 0.0,
) -> Container:
    return Container(
        container_id=container_id,
        cargo_type=cargo_type,
        requires_power=requires_power,
        inbound_vessel="MV LATE",
        onward_vessel=onward_vessel,
        yard_block=yard_block,
        handling_hours=handling_hours,
    )


def make_block(
    block_id: str = "B1",
    container_capacity: int = 50,
    reefer_plugs: int = 10,
    initial_containers: int = 0,
    initial_reefers_on_power: int = 0,
) -> YardBlock:
    return YardBlock(
        block_id=block_id,
        container_capacity=container_capacity,
        reefer_plugs=reefer_plugs,
        initial_containers=initial_containers,
        initial_reefers_on_power=initial_reefers_on_power,
    )


def make_world(
    containers: list[Container],
    vessels: list[Vessel] | None = None,
    yard_blocks: list[YardBlock] | None = None,
    alternative_sailings: list[AlternativeSailing] | None = None,
    cost_rates: CostRates | None = None,
) -> WorldFixture:
    if vessels is None:
        vessels = [
            Vessel(
                name="MV LATE",
                role=VesselRole.INBOUND,
                port_call="PSA-TEST",
                eta=BASE,
                etd=BASE + timedelta(hours=36),
            ),
            Vessel(
                name="MV OUT",
                role=VesselRole.OUTBOUND,
                port_call="PSA-TEST",
                eta=BASE + timedelta(hours=10),
                etd=BASE + timedelta(hours=30),
                connection_cutoff=BASE + timedelta(hours=26),
            ),
        ]
    return WorldFixture(
        seed=1,
        terminal="PSA-TEST",
        vessels=vessels,
        yard_blocks=yard_blocks or [make_block()],
        containers=containers,
        alternative_sailings=alternative_sailings or [],
        cost_rates=cost_rates
        or CostRates(
            dwell_per_container_hour=2.0,
            reefer_risk_per_hour=5.0,
            missed_connection_penalty=100.0,
            crane_hour=50.0,
            rebooking_fee=25.0,
        ),
        synthetic_notice="Synthetic test data.",
    )


def outbound_vessel(name: str, cutoff: datetime, etd: datetime | None = None) -> Vessel:
    return Vessel(
        name=name,
        role=VesselRole.OUTBOUND,
        port_call="PSA-TEST",
        eta=cutoff - timedelta(hours=6),
        etd=etd or (cutoff + timedelta(hours=4)),
        connection_cutoff=cutoff,
    )


def inbound_vessel_fixture() -> Vessel:
    return Vessel(
        name="MV LATE",
        role=VesselRole.INBOUND,
        port_call="PSA-TEST",
        eta=BASE,
        etd=BASE + timedelta(hours=36),
    )
