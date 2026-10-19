from __future__ import annotations

import os
from typing import Any


def recommendation_mode() -> str:
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_API_KEY"):
        return "ai"
    return "demo"


def score_match(profile: dict[str, Any], opportunity: dict[str, Any]) -> tuple[int, list[str], bool]:
    volunteer_skills = {s.lower() for s in profile.get("skills") or []}
    required = {s.lower() for s in opportunity.get("required_skills") or []}
    vol_avail = {s.lower() for s in profile.get("availability") or []}
    opp_avail = {s.lower() for s in opportunity.get("availability") or []}
    location_match = (profile.get("location") or "").strip().lower() == (
        opportunity.get("location") or ""
    ).strip().lower()

    skill_hits = volunteer_skills & required
    avail_hits = vol_avail & opp_avail
    eligible = bool(skill_hits) and bool(avail_hits)

    score = 0
    reasons: list[str] = []
    if required:
        score += int(100 * len(skill_hits) / len(required))
    if skill_hits:
        reasons.append("Skills overlap: " + ", ".join(sorted(skill_hits)))
    else:
        reasons.append("Missing required skills")

    if avail_hits:
        score += 20
        reasons.append("Available: " + ", ".join(sorted(avail_hits)))
    else:
        reasons.append("Availability does not overlap")

    if location_match:
        score += 15
        reasons.append("Same location")

    remaining = opportunity.get("capacity", 0) - opportunity.get("filled", 0)
    if remaining <= 0:
        eligible = False
        reasons.append("Opportunity is full")
    elif remaining == 1:
        reasons.append("One seat left")

    return min(score, 100), reasons, eligible
