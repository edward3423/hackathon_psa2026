"""Mocked action dispatch and validation (PRD 9.15).

Actions are derived deterministically from an approved plan: no uuids, no
clock reads. Validation accepts only actions that byte-for-byte match what
the approved plan derives, and rejects everything else with a reason.
"""

from cascade.contracts import (
    ActionReceipt,
    ActionReceiptStatus,
    CargoType,
    MockedAction,
    MockedActionType,
    RecoveryActionType,
    RecoveryPlan,
)

_ID_PREFIX: dict[MockedActionType, str] = {
    MockedActionType.TERMINAL_WORK_ORDER: "WO",
    MockedActionType.REEFER_CHECK: "RC",
    MockedActionType.CARRIER_NOTICE: "CN",
}


def build_actions(plan: RecoveryPlan) -> list[MockedAction]:
    """Derive the mocked action sequence for an approved plan.

    For each plan action, in plan order:
    - a TERMINAL_WORK_ORDER (WO-001, WO-002, ...) always;
    - a REEFER_CHECK (RC-...) when the cargo is pharma reefer;
    - a CARRIER_NOTICE (CN-...) when the action rebooks onto another sailing.
    Identifiers are sequential per type, so equal plans yield equal actions.
    """
    counters = dict.fromkeys(_ID_PREFIX, 0)

    def make(action_type: MockedActionType, description: str, payload_summary: str) -> MockedAction:
        counters[action_type] += 1
        return MockedAction(
            action_id=f"{_ID_PREFIX[action_type]}-{counters[action_type]:03d}",
            action_type=action_type,
            plan_archetype=plan.archetype,
            description=description,
            payload_summary=payload_summary,
        )

    actions: list[MockedAction] = []
    for plan_action in plan.actions:
        payload = (
            f"action={plan_action.action.value}; vessel={plan_action.onward_vessel}; "
            f"cargo={plan_action.cargo_type.value}; count={plan_action.container_count}; "
            f"target={plan_action.target_sailing or '-'}"
        )
        actions.append(
            make(
                MockedActionType.TERMINAL_WORK_ORDER,
                (
                    f"{plan_action.action.value} {plan_action.container_count} "
                    f"{plan_action.cargo_type.value} containers for "
                    f"{plan_action.onward_vessel}"
                ),
                payload,
            )
        )
        if plan_action.cargo_type is CargoType.PHARMA_REEFER:
            actions.append(
                make(
                    MockedActionType.REEFER_CHECK,
                    (
                        f"Verify power and temperature for "
                        f"{plan_action.container_count} pharma reefers "
                        f"({plan_action.action.value} for {plan_action.onward_vessel})"
                    ),
                    payload,
                )
            )
        if plan_action.action is RecoveryActionType.REBOOK:
            actions.append(
                make(
                    MockedActionType.CARRIER_NOTICE,
                    (
                        f"Notify carrier: rebook {plan_action.container_count} "
                        f"{plan_action.cargo_type.value} containers from "
                        f"{plan_action.onward_vessel} to "
                        f"{plan_action.target_sailing or 'unspecified sailing'}"
                    ),
                    payload,
                )
            )
    return actions


def validate_actions(plan: RecoveryPlan, actions: list[MockedAction]) -> list[ActionReceipt]:
    """Accept only actions derivable from the approved plan.

    An action is accepted when its id and full content match the action that
    ``build_actions`` derives from the plan, exactly once. Unknown ids,
    tampered content, and duplicates are rejected with a reason. Accepted
    actions get the deterministic receipt reference RCPT-<action_id>.
    """
    expected = {action.action_id: action for action in build_actions(plan)}
    seen: set[str] = set()
    receipts: list[ActionReceipt] = []
    for action in actions:
        reference = expected.get(action.action_id)
        if reference is None:
            receipts.append(
                ActionReceipt(
                    action_id=action.action_id,
                    status=ActionReceiptStatus.REJECTED,
                    receipt_ref=None,
                    detail="rejected: action is not derivable from the approved plan",
                )
            )
        elif action.action_id in seen:
            receipts.append(
                ActionReceipt(
                    action_id=action.action_id,
                    status=ActionReceiptStatus.REJECTED,
                    receipt_ref=None,
                    detail="rejected: duplicate dispatch of an already-processed action",
                )
            )
        elif action != reference:
            receipts.append(
                ActionReceipt(
                    action_id=action.action_id,
                    status=ActionReceiptStatus.REJECTED,
                    receipt_ref=None,
                    detail="rejected: action content does not match the approved plan",
                )
            )
        else:
            seen.add(action.action_id)
            receipts.append(
                ActionReceipt(
                    action_id=action.action_id,
                    status=ActionReceiptStatus.ACCEPTED,
                    receipt_ref=f"RCPT-{action.action_id}",
                    detail=f"accepted: {action.action_type.value} dispatched (mock)",
                )
            )
    return receipts
