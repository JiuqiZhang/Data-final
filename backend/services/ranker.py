import asyncio
from urllib.parse import urlparse, parse_qs

from services import gemini_service


# ── Scoring weights (Stage 2 composite) ─────────────────────────────────────
# All four weights must sum to 1.0. Adjust here to tune signal importance.
SCORE_WEIGHTS = {
    "channel_trust":   0.20,
    "title_relevance": 0.30,
    "engagement":      0.25,
    "recency":         0.25,
}

# Stage 3 blend: final = STAGE2_WEIGHT * composite + (1 - STAGE2_WEIGHT) * llm_norm
STAGE2_WEIGHT = 0.70

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


def _video_id(url: str) -> str:
    """Return the YouTube video ID for youtube.com URLs, else the full URL."""
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc:
        vid = parse_qs(parsed.query).get("v", [None])[0]
        if vid:
            return vid
    return url


def _infer_level_by_title(title: str) -> str:
    lower = title.lower()
    if any(kw in lower for kw in (
        "introduction", "intro", "beginner", "fundamentals", "basics",
        "getting started", "101", "crash course", "from scratch", "for beginners",
        "zero to", "overview", "complete guide", "first steps",
    )):
        return "beginner"
    if any(kw in lower for kw in (
        "advanced", "deep dive", "research", "expert", "mastering",
        "optimization", "production", "at scale", "architecture", "internals",
        "fine-tuning", "finetuning", "deployment", "best practices", "under the hood",
    )):
        return "advanced"
    if any(kw in lower for kw in (
        "practical", "hands-on", "hands on", "project", "build", "implement",
        "in practice", "real world", "in depth", "walkthrough", "applied",
    )):
        return "intermediate"
    return "intermediate"


def _title_relevance(title: str, skill: str) -> float:
    skill_tokens = set(skill.lower().split())
    title_tokens = set(title.lower().split())
    if not skill_tokens:
        return 0.0
    direct = len(skill_tokens & title_tokens) / len(skill_tokens)
    if direct > 0:
        return direct
    # Partial credit: skill token is a prefix of a title token (e.g. "go" → "golang")
    partial = sum(
        1 for s in skill_tokens
        if any(t.startswith(s) or s.startswith(t) for t in title_tokens)
    )
    return 0.7 * partial / len(skill_tokens)


def _compute_stage2_score(resource: dict) -> float:
    """
    Composite of four normalised signals (each 0–1), weighted by SCORE_WEIGHTS.
    Result is 0–1.
    """
    ct = resource.get("source_trust", 0.5)
    tr = _title_relevance(resource.get("title", ""), resource.get("skill_addressed", ""))
    er = resource.get("engagement_ratio", 0.0)
    rc = resource.get("recency_score", 0.5)
    w = SCORE_WEIGHTS
    return (ct * w["channel_trust"]
            + tr * w["title_relevance"]
            + er * w["engagement"]
            + rc * w["recency"])


async def build_learning_path(
    all_resources: list[dict],
    skill_gaps: list[dict],
    max_per_level: int = 5,
    max_per_gap: int = 2,
) -> list[dict]:
    """
    Three-stage pipeline:
      Stage 1 — hard pre-filters already applied in youtube_service.search_youtube.
      Stage 2 — 4-signal composite score (channel trust, title relevance,
                 engagement ratio, recency).
      Stage 3 — LLM evaluates video descriptions; blended into final score.
    Returns list of resource dicts with rank, level, score, description_score, reason.
    """
    if not all_resources:
        return []

    # Attach priority from the corresponding skill gap
    priority_map = {g["skill"].lower(): g["priority"] for g in skill_gaps}
    for r in all_resources:
        r["priority"] = priority_map.get(r.get("skill_addressed", "").lower(), "low")

    # Sort high → medium → low so first occurrence wins during deduplication
    all_resources.sort(key=lambda r: _PRIORITY_ORDER.get(r["priority"], 2))

    # Deduplicate by video ID (YouTube) or URL — keep highest-priority occurrence
    seen: set[str] = set()
    deduped: list[dict] = []
    for r in all_resources:
        key = _video_id(r.get("url", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    all_resources = deduped

    # ── Stage 2: compute composite score ────────────────────────────────────
    for r in all_resources:
        r["stage2_score"] = _compute_stage2_score(r)

    # ── Gemini level tagging + Stage 3 description eval (parallel) ─────────────
    gemini_input = [
        {
            "index": i,
            "title": r["title"],
            "source": r["source"],
            "skill_addressed": r.get("skill_addressed", ""),
        }
        for i, r in enumerate(all_resources)
    ]
    yt_resources = [
        {
            "resource_index": i,
            "title": r["title"],
            "description": r.get("description", "")[:800],  # trim for token budget
            "skill_addressed": r.get("skill_addressed", ""),
        }
        for i, r in enumerate(all_resources)
        if r.get("source") == "YouTube"
    ]
    tag_result, desc_result = await asyncio.gather(
        gemini_service.tag_resources(skill_gaps, gemini_input),
        gemini_service.evaluate_descriptions(skill_gaps, yt_resources),
        return_exceptions=True,
    )
    tag_map = {t["resource_index"]: t for t in tag_result} if isinstance(tag_result, list) else {}
    desc_map = {e["resource_index"]: e for e in desc_result} if isinstance(desc_result, list) else {}

    for i, r in enumerate(all_resources):
        tag = tag_map.get(i, {})
        # Normalise Gemini output: lowercase + strip, then validate against known values
        raw = tag.get("level", "")
        gemini_level = raw.lower().strip() if raw.lower().strip() in LEVEL_ORDER else None
        r["level"] = (
            gemini_level
            or r.get("level_hint")
            or _infer_level_by_title(r["title"])
        )
        r["justification"] = tag.get("justification", "")

    for i, r in enumerate(all_resources):
        eval_result = desc_map.get(i, {})
        llm_score = eval_result.get("relevance_score", 5)  # default neutral if missing
        r["description_score"] = llm_score
        r["description_reason"] = eval_result.get("reason", "")
        # Blend Stage 2 + Stage 3 into final score
        llm_norm = llm_score / 10.0
        r["raw_score"] = (STAGE2_WEIGHT * r["stage2_score"]
                          + (1 - STAGE2_WEIGHT) * llm_norm)

    # ── Bucket by level, cap per level ──────────────────────────────────────
    buckets: dict[str, list] = {"beginner": [], "intermediate": [], "advanced": []}
    for r in all_resources:
        lvl = r.get("level", "intermediate")
        if lvl not in buckets:
            lvl = "intermediate"
        buckets[lvl].append(r)

    ranked: list[dict] = []
    for lvl in ("beginner", "intermediate", "advanced"):
        sorted_bucket = sorted(buckets[lvl], key=lambda x: x["raw_score"], reverse=True)
        gap_counts: dict[str, int] = {}
        selected: list[dict] = []
        for r in sorted_bucket:
            if len(selected) >= max_per_level:
                break
            skill = r.get("skill_addressed", "")
            if gap_counts.get(skill, 0) < max_per_gap:
                selected.append(r)
                gap_counts[skill] = gap_counts.get(skill, 0) + 1
        ranked.extend(selected)

    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    return ranked
