"""Descriptive reference-path checks, deliberately not Petri-net alignments."""

from collections import defaultdict
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source: str = Field(min_length=1, max_length=200)
    target: str = Field(min_length=1, max_length=200)


class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_starts: list[str] = Field(min_length=1, max_length=200)
    allowed_ends: list[str] = Field(min_length=1, max_length=200)
    allowed_edges: list[Edge] = Field(max_length=2000)

    @field_validator("allowed_starts", "allowed_ends")
    @classmethod
    def valid_names(cls, values):
        if any(not v.strip() or len(v) > 200 for v in values):
            raise ValueError(
                "Reference activities must be nonblank and at most 200 characters"
            )
        values = [v.strip() for v in values]
        if len(values) != len(set(values)):
            raise ValueError("Reference start/end activities must be unique")
        return values


def conformance(events, reference, limit):
    edges = {(e.source, e.target) for e in reference.allowed_edges}
    if len(edges) != len(reference.allowed_edges):
        raise ValueError("Reference edges must be unique")
    starts = set(reference.allowed_starts)
    ends = set(reference.allowed_ends)
    cases = defaultdict(list)
    for i, event in enumerate(events):
        cases[event.case_id].append((event.timestamp, i, event.activity))
    details = []
    conforming = 0
    counts = {"disallowed_start": 0, "disallowed_end": 0, "disallowed_edge": 0}
    total = 0
    for case_id, trace in sorted(cases.items()):
        trace.sort()
        violations = []
        case_total = 0

        def add(kind, **fields):
            nonlocal case_total, total
            counts[kind] += 1
            case_total += 1
            total += 1
            if len(violations) < 50:
                violations.append({"kind": kind, **fields})

        if trace[0][2] not in starts:
            add("disallowed_start", activity=trace[0][2])
        if trace[-1][2] not in ends:
            add("disallowed_end", activity=trace[-1][2])
        for position, (a, b) in enumerate(zip(trace, trace[1:]), start=1):
            if (a[2], b[2]) not in edges:
                add(
                    "disallowed_edge",
                    source=a[2],
                    target=b[2],
                    transition_index=position,
                )
        conforming += case_total == 0
        if len(details) < limit:
            details.append(
                {
                    "case_id": case_id,
                    "conforming": case_total == 0,
                    "violation_count": case_total,
                    "violations": violations,
                    "violations_truncated": case_total > len(violations),
                }
            )
    return {
        "case_count": len(cases),
        "conforming_cases": conforming,
        "violating_cases": len(cases) - conforming,
        "conformance_ratio": conforming / len(cases),
        "violation_count": total,
        "violation_counts": counts,
        "case_details": details,
        "case_details_truncated": len(cases) > len(details),
        "case_details_limit": limit,
        "reference": reference.model_dump(),
        "method": "A case conforms only when its first activity, last activity and every adjacent chronological transition occur in the supplied allowlists. All observed cases counted; drilldown bounded. Equal timestamps preserve input order. Descriptive reference conformance only, not Petri-net token replay, edit-distance alignment, compliance certification or causal assessment.",
    }
