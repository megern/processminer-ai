"""Directly-follows analysis on timestamped case event logs."""

from collections import defaultdict, Counter
from datetime import datetime
from statistics import mean, median
from math import floor
from pydantic import BaseModel, ConfigDict, Field
from .conformance import Reference, conformance


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=1, max_length=200)
    activity: str = Field(min_length=1, max_length=200)
    timestamp: datetime


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[Event] = Field(min_length=1, max_length=10000)
    case_limit: int = Field(default=50, ge=1, le=200)
    reference: Reference | None = None


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
    case_details = []
    cases_with_rework = 0
    total_rework_events = 0
    for case_id, trace in sorted(cases.items()):
        trace.sort()
        variants[tuple(e[2] for e in trace)] += 1
        activities.update(e[2] for e in trace)
        duration = (trace[-1][0] - trace[0][0]).total_seconds()
        durations.append(duration)
        counts = Counter(event[2] for event in trace)
        repetitions = {
            activity: count - 1 for activity, count in counts.items() if count > 1
        }
        rework_events = sum(repetitions.values())
        cases_with_rework += bool(rework_events)
        total_rework_events += rework_events
        if len(case_details) < request.case_limit:
            case_details.append(
                {
                    "case_id": case_id,
                    "event_count": len(trace),
                    "duration_seconds": duration,
                    "variant": [event[2] for event in trace[:50]],
                    "variant_truncated": len(trace) > 50,
                    "rework_events": rework_events,
                    "repeated_activity_count": len(repetitions),
                    "repeated_activities": [
                        {"activity": activity, "extra_visits": count}
                        for activity, count in sorted(repetitions.items())[:50]
                    ],
                    "repeated_activities_truncated": len(repetitions) > 50,
                }
            )
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
    result = {
        "case_count": len(cases),
        "event_count": len(request.events),
        "mean_case_seconds": mean(durations),
        "case_duration_summary": {
            "median_seconds": median(durations),
            "p90_seconds": quantile(durations, 0.90),
            "p95_seconds": quantile(durations, 0.95),
            "method": "Linear interpolation at (n-1)*p across all observed case durations.",
        },
        "rework": {
            "cases_with_rework": cases_with_rework,
            "case_fraction": cases_with_rework / len(cases),
            "extra_activity_visits": total_rework_events,
            "definition": "Occurrences after the first of the same activity within the same case. Repetition may be legitimate; it does not prove error or waste.",
        },
        "case_details": case_details,
        "case_details_limit": request.case_limit,
        "case_details_truncated": len(cases) > len(case_details),
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

    if request.reference is not None:
        result["conformance"] = conformance(
            request.events, request.reference, request.case_limit
        )
    return result


def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
