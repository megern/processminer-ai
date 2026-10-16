"""Directly-follows analysis on timestamped case event logs."""

from collections import defaultdict, Counter
from datetime import datetime
from statistics import mean
from pydantic import BaseModel, ConfigDict, Field


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=1, max_length=200)
    activity: str = Field(min_length=1, max_length=200)
    timestamp: datetime


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[Event] = Field(min_length=1, max_length=10000)


def analyze(request: Request) -> dict:
    cases = defaultdict(list)
    for index, event in enumerate(request.events):
        if event.timestamp.tzinfo is None or event.timestamp.utcoffset() is None:
            raise ValueError("Timestamps must include timezone")
        cases[event.case_id].append((event.timestamp, index, event.activity))
    edges = defaultdict(list)
    variants = Counter()
    activities = Counter()
    durations = []
    tied = 0
    for trace in cases.values():
        trace.sort()
        variants[tuple(e[2] for e in trace)] += 1
        activities.update(e[2] for e in trace)
        durations.append((trace[-1][0] - trace[0][0]).total_seconds())
        for left, right in zip(trace, trace[1:]):
            seconds = (right[0] - left[0]).total_seconds()
            tied += seconds == 0
            edges[(left[2], right[2])].append(seconds)
    relations = [
        {
            "from": a,
            "to": b,
            "count": len(values),
            "mean_seconds": mean(values),
            "total_seconds": sum(values),
        }
        for (a, b), values in sorted(edges.items())
    ]
    candidates = [
        {
            "activity": activity,
            "event_count": count,
            "reason": "Repeated activity; investigate deterministic rules and exception rate before automation.",
        }
        for activity, count in sorted(
            activities.items(), key=lambda item: (-item[1], item[0])
        )
        if count >= 2
    ]
    return {
        "case_count": len(cases),
        "event_count": len(request.events),
        "mean_case_seconds": mean(durations),
        "directly_follows": relations,
        "bottlenecks": sorted(
            relations,
            key=lambda edge: (-edge["mean_seconds"], edge["from"], edge["to"]),
        ),
        "variants": [
            {"activities": list(variant), "case_count": count}
            for variant, count in sorted(
                variants.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "automation_candidates": candidates,
        "tied_timestamp_pairs": tied,
        "limitations": "Intervals include waiting and execution time; they are not activity service durations. Ties preserve input order. Frequency alone does not establish automation feasibility.",
    }
