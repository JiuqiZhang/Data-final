from services import gemini_service


PRIORITY_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}

LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


def _infer_level_by_title(title: str) -> str:
    lower = title.lower()
    if any(kw in lower for kw in ("introduction", "intro", "beginner", "fundamentals", "basics", "getting started", "101")):
        return "beginner"
    if any(kw in lower for kw in ("advanced", "deep dive", "research", "expert", "mastering")):
        return "advanced"
    return "intermediate"


def _title_relevance(title: str, skill: str) -> float:
    skill_tokens = set(skill.lower().split())
    title_tokens = set(title.lower().split())
    if not skill_tokens:
        return 0.0
    return len(skill_tokens & title_tokens) / len(skill_tokens)


def _compute_score(resource: dict, priority: str) -> float:
    pw = PRIORITY_WEIGHT.get(priority, 1.0)
    st = resource.get("source_trust", 0.5)
    tr = _title_relevance(resource.get("title", ""), resource.get("skill_addressed", ""))
    return (pw * 3.0) + (st * 1.5) + (tr * 2.0)


async def build_learning_path(
    all_resources: list[dict],
    skill_gaps: list[dict],
    max_per_level: int = 5,
) -> list[dict]:
    """
    Score, tag, and sort resources into a three-tier learning path.
    Returns list of resource dicts with rank, level, justification, score.
    """
    if not all_resources:
        return []

    # Attach priority from the corresponding skill gap
    priority_map = {g["skill"].lower(): g["priority"] for g in skill_gaps}
    for r in all_resources:
        skill_key = r.get("skill_addressed", "").lower()
        r["priority"] = priority_map.get(skill_key, "low")
        r["raw_score"] = _compute_score(r, r["priority"])

    # Gemini tagging for level + justification
    gemini_input = [
        {
            "index": i,
            "title": r["title"],
            "source": r["source"],
            "skill_addressed": r.get("skill_addressed", ""),
        }
        for i, r in enumerate(all_resources)
    ]
    try:
        tags = await gemini_service.tag_resources(skill_gaps, gemini_input)
        tag_map = {t["resource_index"]: t for t in tags}
    except Exception:
        tag_map = {}

    for i, r in enumerate(all_resources):
        tag = tag_map.get(i, {})
        # Level: prefer Gemini > API metadata hint > title heuristic
        r["level"] = (
            tag.get("level")
            or r.get("level_hint")
            or _infer_level_by_title(r["title"])
        )
        r["justification"] = tag.get("justification", "")

    # Bucket by level
    buckets: dict[str, list] = {"beginner": [], "intermediate": [], "advanced": []}
    for r in all_resources:
        lvl = r.get("level", "intermediate")
        if lvl not in buckets:
            lvl = "intermediate"
        buckets[lvl].append(r)

    # Sort each bucket by score descending, cap at max_per_level
    ranked: list[dict] = []
    for lvl in ("beginner", "intermediate", "advanced"):
        sorted_bucket = sorted(buckets[lvl], key=lambda x: x["raw_score"], reverse=True)
        ranked.extend(sorted_bucket[:max_per_level])

    # Assign final rank positions
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    return ranked
