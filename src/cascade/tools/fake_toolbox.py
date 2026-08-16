"""Deterministic in-repo ToolBox fake.

Produces canned contract objects for the golden MV ATLAS STAR scenario so the
workflow, API, and tests run fully offline without the engine workstream. All
figures shown in trace events flow from these objects, never from separate
hard-coded strings.
"""

from datetime import UTC, datetime, timedelta

from cascade.contracts import (
    ActionReceipt,
    ActionReceiptStatus,
    AlternativeSailing,
    AlternativeSailingResult,
    BlockForecast,
    CargoType,
    Confidence,
    ConnectionAnalysis,
    ConnectionGroupSummary,
    ConnectionStatus,
    ContainerConnection,
    CostComponent,
    CostEstimate,
    MockedAction,
    MockedActionType,
    PlanArchetype,
    PlanComparison,
    PlanEvaluation,
    PlanMetrics,
    PriorityEmphasis,
    RecoveryActionType,
    RecoveryPlan,
    ReeferShortage,
    SailingLookupStatus,
    YardForecast,
    YardOccupancyPoint,
)

REEFER_PLUGS_AVAILABLE = 150
REEFER_PLUGS_REQUIRED_IF_ALL_RUSH = 176
RUSH_REEFER_CAP = REEFER_PLUGS_AVAILABLE - (
    REEFER_PLUGS_REQUIRED_IF_ALL_RUSH - 60
)  # 34 reefers can rush within plug capacity

_BLOCK_CAPACITY = 300
_BLOCK_IDS = ["Y1", "Y2", "Y3", "Y4"]

_PLAN_METRICS: dict[PlanArchetype, dict[str, float]] = {
    PlanArchetype.AGGRESSIVE_RUSH: {
        "dwell": 21000.0,
        "reefer_risk": 9000.0,
        "missed_penalty": 36000.0,
        "crane": 84000.0,
        "rebooking": 34000.0,
        "missed": 26,
        "protected_pct": 100.0,
        "yard_peak_pct": 91.0,
        "delay_hours": 6.0,
    },
    PlanArchetype.STANDARD_REBOOK: {
        "dwell": 43000.0,
        "reefer_risk": 18000.0,
        "missed_penalty": 12000.0,
        "crane": 24000.0,
        "rebooking": 55000.0,
        "missed": 60,
        "protected_pct": 78.0,
        "yard_peak_pct": 88.0,
        "delay_hours": 30.0,
    },
    PlanArchetype.OPTIMIZED_HYBRID: {
        "dwell": 28000.0,
        "reefer_risk": 7500.0,
        "missed_penalty": 18000.0,
        "crane": 41000.0,
        "rebooking": 34000.0,
        "missed": 26,
        "protected_pct": 100.0,
        "yard_peak_pct": 82.0,
        "delay_hours": 12.0,
    },
}


def _cost_estimate(archetype: PlanArchetype) -> CostEstimate:
    m = _PLAN_METRICS[archetype]
    components = [
        CostComponent(name="Additional dwell", amount=m["dwell"], basis="SGD 4 per container hour"),
        CostComponent(name="Reefer risk", amount=m["reefer_risk"], basis="SGD 25 per reefer hour"),
        CostComponent(
            name="Missed-connection penalty",
            amount=m["missed_penalty"],
            basis="SGD 600 per missed connection",
        ),
        CostComponent(name="Extra crane time", amount=m["crane"], basis="SGD 1200 per crane hour"),
        CostComponent(name="Rebooking", amount=m["rebooking"], basis="SGD 250 per rebooked box"),
    ]
    total = sum(component.amount for component in components)
    return CostEstimate(components=components, total=total, illustrative=True)


def _rushed_reefers(plan: RecoveryPlan) -> int:
    return sum(
        action.container_count
        for action in plan.actions
        if action.action == RecoveryActionType.RUSH and action.cargo_type == CargoType.PHARMA_REEFER
    )


class FakeToolBox:
    """Canned deterministic tool results for the golden scenario."""

    def analyse_connections(
        self, revised_eta: datetime, emphasis: PriorityEmphasis
    ) -> ConnectionAnalysis:
        cutoff_meridian = revised_eta + timedelta(hours=3)
        cutoff_blue_dart = revised_eta - timedelta(hours=1)
        cutoff_coral_wind = revised_eta + timedelta(hours=9)
        connections = [
            ContainerConnection(
                container_id="CASU2000001",
                cargo_type=CargoType.PHARMA_REEFER,
                onward_vessel="MV MERIDIAN",
                ready_time=revised_eta + timedelta(hours=1),
                connection_cutoff=cutoff_meridian,
                margin_hours=2.0,
                status=ConnectionStatus.AT_RISK,
                priority_rank=1,
                priority_reason="Pharmaceutical reefer with a 2.0 hour connection margin",
            ),
            ContainerConnection(
                container_id="CASU2000114",
                cargo_type=CargoType.TIME_CRITICAL_MANUFACTURING,
                onward_vessel="MV MERIDIAN",
                ready_time=revised_eta + timedelta(hours=1),
                connection_cutoff=cutoff_meridian,
                margin_hours=2.0,
                status=ConnectionStatus.AT_RISK,
                priority_rank=2,
                priority_reason="Time-critical manufacturing cargo with a 2.0 hour margin",
            ),
            ContainerConnection(
                container_id="CASU2000267",
                cargo_type=CargoType.GENERAL_DRY,
                onward_vessel="MV BLUE DART",
                ready_time=revised_eta + timedelta(hours=1),
                connection_cutoff=cutoff_blue_dart,
                margin_hours=-2.0,
                status=ConnectionStatus.MISSED,
                priority_rank=3,
                priority_reason="General dry cargo whose cutoff has already passed",
            ),
            ContainerConnection(
                container_id="CASU2000331",
                cargo_type=CargoType.GENERAL_DRY,
                onward_vessel="MV CORAL WIND",
                ready_time=revised_eta + timedelta(hours=1),
                connection_cutoff=cutoff_coral_wind,
                margin_hours=8.0,
                status=ConnectionStatus.SAFE,
                priority_rank=4,
                priority_reason="General dry cargo with more than 4 hours of margin",
            ),
        ]
        groups = [
            ConnectionGroupSummary(
                onward_vessel="MV MERIDIAN",
                cargo_type=CargoType.PHARMA_REEFER,
                status=ConnectionStatus.AT_RISK,
                container_count=60,
            ),
            ConnectionGroupSummary(
                onward_vessel="MV MERIDIAN",
                cargo_type=CargoType.TIME_CRITICAL_MANUFACTURING,
                status=ConnectionStatus.AT_RISK,
                container_count=66,
            ),
            ConnectionGroupSummary(
                onward_vessel="MV BLUE DART",
                cargo_type=CargoType.GENERAL_DRY,
                status=ConnectionStatus.MISSED,
                container_count=60,
            ),
            ConnectionGroupSummary(
                onward_vessel="MV BLUE DART",
                cargo_type=CargoType.GENERAL_DRY,
                status=ConnectionStatus.SAFE,
                container_count=84,
            ),
            ConnectionGroupSummary(
                onward_vessel="MV CORAL WIND",
                cargo_type=CargoType.GENERAL_DRY,
                status=ConnectionStatus.SAFE,
                container_count=130,
            ),
        ]
        return ConnectionAnalysis(
            delay_hours=18,
            safe_count=214,
            at_risk_count=126,
            missed_count=60,
            groups=groups,
            connections=connections,
        )

    def simulate_yard(
        self,
        revised_eta: datetime,
        connections: ConnectionAnalysis,
        plan: RecoveryPlan | None,
        horizon_hours: int,
    ) -> YardForecast:
        start = revised_eta.astimezone(UTC) - timedelta(hours=6)
        peak_hour = 41
        baseline_peak = 282  # 94% of 300
        planned_peak = 246  # 82% of 300
        peak = baseline_peak if plan is None else planned_peak
        blocks: list[BlockForecast] = []
        for offset, block_id in enumerate(_BLOCK_IDS):
            series: list[YardOccupancyPoint] = []
            block_peak = peak - offset * 12
            for hour in range(horizon_hours + 1):
                distance = abs(hour - peak_hour)
                occupancy = max(150, block_peak - distance * 3)
                series.append(
                    YardOccupancyPoint(
                        time=start + timedelta(hours=hour),
                        occupancy=occupancy,
                        congested=occupancy >= int(_BLOCK_CAPACITY * 0.85),
                        full=occupancy >= _BLOCK_CAPACITY,
                    )
                )
            blocks.append(
                BlockForecast(
                    block_id=block_id,
                    container_capacity=_BLOCK_CAPACITY,
                    series=series,
                    peak_occupancy=block_peak,
                    peak_time=start + timedelta(hours=peak_hour),
                )
            )
        shortages: list[ReeferShortage] = []
        rushed = REEFER_PLUGS_REQUIRED_IF_ALL_RUSH if plan is None else _rushed_reefers(plan) + 116
        if rushed > REEFER_PLUGS_AVAILABLE:
            shortages.append(
                ReeferShortage(
                    block_id="Y2",
                    start_time=revised_eta + timedelta(hours=6),
                    required_plugs=rushed,
                    available_plugs=REEFER_PLUGS_AVAILABLE,
                )
            )
        return YardForecast(horizon_hours=horizon_hours, blocks=blocks, reefer_shortages=shortages)

    def find_alternative_sailings(self, force_timeout: bool) -> AlternativeSailingResult:
        sailings = [
            AlternativeSailing(
                vessel_name="MV NOVA TRADER",
                replaces_onward_vessel="MV MERIDIAN",
                departs=datetime(2026, 9, 16, 20, 0, tzinfo=UTC),
                connection_cutoff=datetime(2026, 9, 16, 12, 0, tzinfo=UTC),
                available_capacity=140,
            ),
            AlternativeSailing(
                vessel_name="MV EASTERN LOOP",
                replaces_onward_vessel="MV BLUE DART",
                departs=datetime(2026, 9, 17, 6, 0, tzinfo=UTC),
                connection_cutoff=datetime(2026, 9, 16, 22, 0, tzinfo=UTC),
                available_capacity=180,
            ),
        ]
        if force_timeout:
            return AlternativeSailingResult(
                status=SailingLookupStatus.TIMEOUT_CACHED_FALLBACK,
                sailings=sailings,
                stale_notice=(
                    "Live sailing lookup timed out; using the cached synthetic snapshot "
                    "from 2026-09-12T00:00Z, which may be stale."
                ),
            )
        return AlternativeSailingResult(
            status=SailingLookupStatus.MOCK_SUCCESS, sailings=sailings, stale_notice=None
        )

    def evaluate_plan(
        self,
        revised_eta: datetime,
        connections: ConnectionAnalysis,
        plan: RecoveryPlan,
        emphasis: PriorityEmphasis,
    ) -> PlanEvaluation:
        rushed_reefers = _rushed_reefers(plan)
        rejection_reasons: list[str] = []
        if rushed_reefers > RUSH_REEFER_CAP:
            rejection_reasons.append(
                f"Rushing {rushed_reefers} pharmaceutical reefers needs "
                f"{REEFER_PLUGS_REQUIRED_IF_ALL_RUSH} reefer plugs but only "
                f"{REEFER_PLUGS_AVAILABLE} are available; rush at most {RUSH_REEFER_CAP}."
            )
        metrics = _PLAN_METRICS[plan.archetype]
        return PlanEvaluation(
            plan=plan,
            metrics=PlanMetrics(
                cost=_cost_estimate(plan.archetype),
                missed_connections=int(metrics["missed"]),
                critical_cargo_protected_pct=metrics["protected_pct"],
                yard_peak_occupancy_pct=metrics["yard_peak_pct"],
                max_additional_delay_hours=metrics["delay_hours"],
            ),
            feasible=not rejection_reasons,
            rejection_reasons=rejection_reasons,
        )

    def compare_plans(
        self,
        revised_eta: datetime,
        connections: ConnectionAnalysis,
        plans: list[RecoveryPlan],
        emphasis: PriorityEmphasis,
        confidence: Confidence,
    ) -> PlanComparison:
        evaluations = [
            self.evaluate_plan(revised_eta, connections, plan, emphasis) for plan in plans
        ]
        feasible = [evaluation for evaluation in evaluations if evaluation.feasible]
        recommended = None
        rationale = "No feasible plan; revision required."
        if feasible:
            best = min(
                feasible,
                key=lambda evaluation: (
                    -evaluation.metrics.critical_cargo_protected_pct,
                    evaluation.metrics.missed_connections,
                    evaluation.metrics.yard_peak_occupancy_pct,
                    evaluation.metrics.cost.total,
                ),
            )
            recommended = best.plan.archetype
            rationale = (
                f"{best.plan.archetype.value} protects "
                f"{best.metrics.critical_cargo_protected_pct:.0f}% of critical cargo with "
                f"{best.metrics.missed_connections} missed connections, a "
                f"{best.metrics.yard_peak_occupancy_pct:.0f}% yard peak, and an illustrative "
                f"cost of SGD {best.metrics.cost.total:,.0f}."
            )
            if confidence is Confidence.MEDIUM:
                rationale += " Confidence is MEDIUM because cached sailing data was used."
        return PlanComparison(
            evaluations=evaluations,
            recommended=recommended,
            rationale=rationale,
            confidence=confidence,
        )

    def build_actions(self, plan: RecoveryPlan) -> list[MockedAction]:
        actions: list[MockedAction] = []
        needs_reefer_check = False
        for index, plan_action in enumerate(plan.actions, start=1):
            if plan_action.action == RecoveryActionType.RUSH:
                action_type = MockedActionType.TERMINAL_WORK_ORDER
                description = (
                    f"Rush {plan_action.container_count} {plan_action.cargo_type.value} "
                    f"containers to meet {plan_action.onward_vessel}."
                )
            else:
                action_type = MockedActionType.CARRIER_NOTICE
                target = plan_action.target_sailing or "a later synthetic sailing"
                description = (
                    f"Rebook {plan_action.container_count} {plan_action.cargo_type.value} "
                    f"containers from {plan_action.onward_vessel} to {target}."
                )
            if plan_action.cargo_type == CargoType.PHARMA_REEFER:
                needs_reefer_check = True
            actions.append(
                MockedAction(
                    action_id=f"act-{plan.archetype.value.lower()}-{index:02d}",
                    action_type=action_type,
                    plan_archetype=plan.archetype,
                    description=description,
                    payload_summary=(
                        f"{plan_action.action.value} {plan_action.container_count} x "
                        f"{plan_action.cargo_type.value} ({plan_action.onward_vessel})"
                    ),
                )
            )
        if needs_reefer_check:
            actions.append(
                MockedAction(
                    action_id=f"act-{plan.archetype.value.lower()}-{len(actions) + 1:02d}",
                    action_type=MockedActionType.REEFER_CHECK,
                    plan_archetype=plan.archetype,
                    description="Verify reefer plug assignments before movement.",
                    payload_summary=f"Confirm plugs within the {REEFER_PLUGS_AVAILABLE}-plug limit",
                )
            )
        return actions

    def validate_actions(
        self, plan: RecoveryPlan, actions: list[MockedAction]
    ) -> list[ActionReceipt]:
        receipts: list[ActionReceipt] = []
        for action in actions:
            if action.plan_archetype != plan.archetype:
                receipts.append(
                    ActionReceipt(
                        action_id=action.action_id,
                        status=ActionReceiptStatus.REJECTED,
                        receipt_ref=None,
                        detail="Action does not belong to the approved plan.",
                    )
                )
                continue
            receipts.append(
                ActionReceipt(
                    action_id=action.action_id,
                    status=ActionReceiptStatus.ACCEPTED,
                    receipt_ref=f"rcpt-{action.action_id}",
                    detail=f"Mocked {action.action_type.value} accepted by the synthetic terminal.",
                )
            )
        return receipts
