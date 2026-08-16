from cascade.contracts import (
    ActionReceiptStatus,
    CargoType,
    MockedAction,
    MockedActionType,
    PlanAction,
    PlanArchetype,
    RecoveryActionType,
    RecoveryPlan,
)
from cascade.engine import build_actions, validate_actions


def hybrid_plan() -> RecoveryPlan:
    return RecoveryPlan(
        archetype=PlanArchetype.OPTIMIZED_HYBRID,
        title="Hybrid",
        actions=[
            PlanAction(
                action=RecoveryActionType.RUSH,
                onward_vessel="MV GONE",
                cargo_type=CargoType.PHARMA_REEFER,
                container_count=2,
                target_sailing=None,
                rationale="protect pharma",
            ),
            PlanAction(
                action=RecoveryActionType.REBOOK,
                onward_vessel="MV GONE",
                cargo_type=CargoType.GENERAL_DRY,
                container_count=3,
                target_sailing="ALT ONE",
                rationale="rebook dry cargo",
            ),
        ],
    )


def test_build_actions_is_deterministic_with_sequential_ids():
    plan = hybrid_plan()
    first = build_actions(plan)
    second = build_actions(plan)
    assert first == second
    assert [action.action_id for action in first] == [
        "WO-001",  # rush work order
        "RC-001",  # reefer check for pharma
        "WO-002",  # rebook work order
        "CN-001",  # carrier notice for rebooking
    ]
    assert [action.action_type for action in first] == [
        MockedActionType.TERMINAL_WORK_ORDER,
        MockedActionType.REEFER_CHECK,
        MockedActionType.TERMINAL_WORK_ORDER,
        MockedActionType.CARRIER_NOTICE,
    ]
    assert all(action.plan_archetype is PlanArchetype.OPTIMIZED_HYBRID for action in first)
    assert "target=ALT ONE" in first[3].payload_summary


def test_validate_accepts_derived_actions_with_deterministic_receipts():
    plan = hybrid_plan()
    actions = build_actions(plan)
    receipts = validate_actions(plan, actions)
    assert len(receipts) == len(actions)
    assert all(receipt.status is ActionReceiptStatus.ACCEPTED for receipt in receipts)
    assert [receipt.receipt_ref for receipt in receipts] == [
        f"RCPT-{action.action_id}" for action in actions
    ]
    assert receipts == validate_actions(plan, actions)


def test_validate_rejects_action_not_in_plan():
    plan = hybrid_plan()
    rogue = MockedAction(
        action_id="WO-099",
        action_type=MockedActionType.TERMINAL_WORK_ORDER,
        plan_archetype=PlanArchetype.OPTIMIZED_HYBRID,
        description="Unload everything early",
        payload_summary="action=RUSH; vessel=MV GONE; cargo=GENERAL_DRY; count=99; target=-",
    )
    receipts = validate_actions(plan, [*build_actions(plan), rogue])
    assert receipts[-1].status is ActionReceiptStatus.REJECTED
    assert receipts[-1].receipt_ref is None
    assert "not derivable" in receipts[-1].detail


def test_validate_rejects_tampered_action_content():
    plan = hybrid_plan()
    actions = build_actions(plan)
    tampered = actions[0].model_copy(update={"payload_summary": "count=999"})
    receipts = validate_actions(plan, [tampered])
    assert receipts[0].status is ActionReceiptStatus.REJECTED
    assert "does not match" in receipts[0].detail


def test_validate_rejects_duplicate_dispatch():
    plan = hybrid_plan()
    actions = build_actions(plan)
    receipts = validate_actions(plan, [actions[0], actions[0]])
    assert receipts[0].status is ActionReceiptStatus.ACCEPTED
    assert receipts[1].status is ActionReceiptStatus.REJECTED
    assert "duplicate" in receipts[1].detail
