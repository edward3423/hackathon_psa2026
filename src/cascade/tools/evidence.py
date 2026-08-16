"""retrieve_context seam over the reviewed local evidence pack.

Reads fixtures/evidence_pack.json through the fixtures loader when the
fixtures workstream has delivered it, and otherwise serves a small reviewed
in-repo fallback so the tool always answers offline.
"""

from typing import Any

_FALLBACK_FACTS: list[dict[str, str]] = [
    {
        "fact": (
            "PSA International handled about 100 million TEUs (twenty-foot equivalent "
            "units) across its global terminal network in 2024."
        ),
        "source": "PSA International Annual and Sustainability Report 2025",
        "url": "https://annualreport.globalpsa.com/",
    },
    {
        "fact": (
            "PSA Singapore is one of the world's largest transshipment hubs, where "
            "containers arrive on one vessel and depart on another."
        ),
        "source": "PSA Singapore Sustainability Report 2025",
        "url": "https://www.singaporepsa.com/wp-content/uploads/2026/06/PSA-SG-Sustainability-Report-2025.pdf",
    },
    {
        "fact": (
            "The Maritime and Port Authority of Singapore publishes monthly vessel "
            "arrival tonnage and container throughput statistics."
        ),
        "source": "MPA Port Statistics",
        "url": "https://www.mpa.gov.sg/who-we-are/newsroom-resources/research-and-statistics/port-statistics",
    },
    {
        "fact": (
            "UN/LOCODE SGSIN identifies the Port of Singapore in international "
            "trade and transport documents."
        ),
        "source": "UN/LOCODE",
        "url": "https://unlocode.unece.org/publications/",
    },
]


def _load_pack() -> list[dict[str, str]]:
    try:
        import cascade.fixtures as fixtures

        load_evidence_pack = getattr(fixtures, "load_evidence_pack")  # noqa: B009
        pack = load_evidence_pack()
    except Exception:
        return list(_FALLBACK_FACTS)
    if hasattr(pack, "model_dump"):
        pack = pack.model_dump(mode="json")
    facts = pack.get("facts", []) if isinstance(pack, dict) else pack
    return [dict(fact) for fact in facts] if facts else list(_FALLBACK_FACTS)


def retrieve_context(query: str) -> dict[str, Any]:
    """Return short reviewed facts with source links for a query."""
    facts = _load_pack()
    words = [word for word in query.lower().split() if len(word) > 3]
    matched = [
        fact for fact in facts if any(word in str(fact.get("fact", "")).lower() for word in words)
    ]
    return {
        "query": query,
        "facts": matched or facts[:3],
        "notice": "Reviewed public evidence pack; agents must not browse the internet.",
    }
