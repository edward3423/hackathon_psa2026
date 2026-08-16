import importlib.util
import sys
from datetime import timedelta
from pathlib import Path
from types import ModuleType

import pytest

from cascade.contracts import CargoType, VesselRole, WorldFixture
from cascade.fixtures import load_evidence_pack, load_golden_world

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    path = ROOT / "scripts" / "generate_fixture.py"
    spec = importlib.util.spec_from_file_location("generate_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def world() -> WorldFixture:
    return load_golden_world()


def margin_hours(world: WorldFixture, container_index: int, delay_hours: int) -> float | None:
    container = world.containers[container_index]
    if container.onward_vessel is None:
        return None
    vessels = {vessel.name: vessel for vessel in world.vessels}
    inbound = vessels[container.inbound_vessel]
    cutoff = vessels[container.onward_vessel].connection_cutoff
    assert cutoff is not None
    ready = inbound.eta + timedelta(hours=delay_hours + container.handling_hours)
    return (cutoff - ready).total_seconds() / 3600


def classify(margin: float) -> str:
    if margin > 4:
        return "SAFE"
    if margin >= 0:
        return "AT_RISK"
    return "MISSED"


def test_committed_world_validates_and_matches_generator(generator: ModuleType) -> None:
    committed = (ROOT / "fixtures" / "golden_world.json").read_text(encoding="utf-8")
    regenerated = generator.render_world_json(generator.build_world())

    assert WorldFixture.model_validate_json(committed)
    assert committed == regenerated


def test_generation_is_deterministic(generator: ModuleType) -> None:
    first = generator.build_world()
    second = generator.build_world()

    assert first == second


def test_container_count_in_prd_range(world: WorldFixture) -> None:
    assert 300 <= len(world.containers) <= 500


def test_exactly_sixty_pharma_reefers_on_power(world: WorldFixture) -> None:
    reefers = [c for c in world.containers if c.cargo_type is CargoType.PHARMA_REEFER]

    assert len(reefers) == 60
    assert all(c.requires_power for c in reefers)
    assert all(not c.requires_power for c in world.containers if c not in reefers)


def test_eighteen_hour_delay_produces_all_three_classifications(world: WorldFixture) -> None:
    statuses = {
        classify(margin)
        for index in range(len(world.containers))
        if (margin := margin_hours(world, index, 18)) is not None
    }

    assert statuses == {"SAFE", "AT_RISK", "MISSED"}


def test_reefer_plugs_are_scarcer_than_reefers(world: WorldFixture) -> None:
    assert sum(block.reefer_plugs for block in world.yard_blocks) < 60


def test_referential_integrity(world: WorldFixture) -> None:
    block_ids = {block.block_id for block in world.yard_blocks}
    vessel_names = {vessel.name for vessel in world.vessels}

    for container in world.containers:
        assert container.yard_block in block_ids
        assert container.inbound_vessel in vessel_names
        assert container.onward_vessel is None or container.onward_vessel in vessel_names


def test_every_affected_outbound_vessel_has_an_alternative(world: WorldFixture) -> None:
    affected = {
        world.containers[index].onward_vessel
        for index in range(len(world.containers))
        if (margin := margin_hours(world, index, 18)) is not None and classify(margin) != "SAFE"
    }
    replacements = {sailing.replaces_onward_vessel for sailing in world.alternative_sailings}

    assert affected
    assert affected <= replacements
    for sailing in world.alternative_sailings:
        replaced = next(v for v in world.vessels if v.name == sailing.replaces_onward_vessel)
        assert replaced.role is VesselRole.OUTBOUND
        assert sailing.departs > replaced.etd
        assert sailing.available_capacity > 0


def test_evidence_pack_shape() -> None:
    pack = load_evidence_pack()
    facts = pack["facts"]

    assert 8 <= len(facts) <= 15
    for fact in facts:
        assert fact["fact"].strip()
        assert fact["source_title"].strip()
        assert fact["source_url"].startswith("https://")
