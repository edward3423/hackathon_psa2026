"""``frontend/src/data/scenarioPreview.generated.ts`` must stay the engine's answer.

The Command Center shows this table before a run and the engine's live analysis
during one. They are the same numbers or the panel contradicts itself, so the
committed file is regenerated with::

    uv run python scripts/export_scenario_preview.py
"""

import json
import re
from typing import Any

from cascade.contracts import PriorityEmphasis, ScenarioControls
from scripts.export_scenario_preview import DELAY_RANGE, OUTPUT_PATH, build_table, render

PREVIEWS_LITERAL = re.compile(
    r"const PREVIEWS: Record<string, ScenarioPreview> = (\{.*?\n\})\n", re.S
)


def _committed_table() -> dict[str, Any]:
    source = OUTPUT_PATH.read_text(encoding="utf-8")
    body = PREVIEWS_LITERAL.search(source)
    assert body is not None, "generated file no longer has a PREVIEWS literal"
    table: dict[str, Any] = json.loads(body.group(1))
    return table


def test_generated_file_matches_the_engine() -> None:
    assert OUTPUT_PATH.read_text(encoding="utf-8") == render(build_table())


def test_table_covers_every_reachable_control_combination() -> None:
    """The frontend lookup has no fallback, so a missing row would be a blank panel."""
    committed = _committed_table()
    expected = {
        f"{delay}:{emphasis.value}" for delay in DELAY_RANGE for emphasis in PriorityEmphasis
    }
    assert set(committed) == expected
    # The delay range must be the one ScenarioControls actually admits.
    bounds = {
        type(constraint).__name__: constraint
        for constraint in ScenarioControls.model_fields["delay_hours"].metadata
    }
    assert DELAY_RANGE.start == bounds["Ge"].ge
    assert DELAY_RANGE.stop - 1 == bounds["Le"].le


def test_every_row_is_internally_consistent() -> None:
    for key, preview in _committed_table().items():
        counts = (preview["safe"], preview["atRisk"], preview["missed"])
        assert sum(counts) == preview["affected"], key
        assert sum(preview["cargo"].values()) == preview["affected"], key
        assert 0 <= preview["yardPeak"] <= 100, key
        assert preview["blocks"], key
