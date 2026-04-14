"""Tests for ranker.py — Stage 2 scoring, level inference, and build_learning_path."""
import pytest
from unittest.mock import AsyncMock, patch

from services.ranker import (
    _infer_level_by_title,
    _title_relevance,
    _compute_stage2_score,
    build_learning_path,
    MIN_SCORE_THRESHOLD,
)


# ── _infer_level_by_title ────────────────────────────────────────────────────

class TestInferLevelByTitle:
    def test_beginner_keywords(self):
        assert _infer_level_by_title("Introduction to Python") == "beginner"
        assert _infer_level_by_title("Python for Beginners") == "beginner"
        assert _infer_level_by_title("Python Crash Course") == "beginner"
        assert _infer_level_by_title("Python 101 Getting Started") == "beginner"
        assert _infer_level_by_title("Zero to Hero: Python Basics") == "beginner"

    def test_advanced_keywords(self):
        assert _infer_level_by_title("Advanced Python Patterns") == "advanced"
        assert _infer_level_by_title("Python at Scale: Production Best Practices") == "advanced"
        assert _infer_level_by_title("Deep Dive into Python Internals") == "advanced"
        assert _infer_level_by_title("Fine-Tuning LLMs for Production") == "advanced"

    def test_intermediate_keywords(self):
        assert _infer_level_by_title("Build a Python Project") == "intermediate"
        assert _infer_level_by_title("Hands-on Python: Real World Applied") == "intermediate"
        assert _infer_level_by_title("Practical Python Walkthrough") == "intermediate"

    def test_default_is_intermediate(self):
        assert _infer_level_by_title("Python Everything You Need") == "intermediate"
        assert _infer_level_by_title("Learn Python") == "intermediate"

    def test_case_insensitive(self):
        assert _infer_level_by_title("INTRODUCTION TO SQL") == "beginner"
        assert _infer_level_by_title("ADVANCED SQL PATTERNS") == "advanced"


# ── _title_relevance ─────────────────────────────────────────────────────────

class TestTitleRelevance:
    def test_exact_match(self):
        score = _title_relevance("Python Tutorial for Data Science", "python")
        assert score == 1.0

    def test_no_match(self):
        score = _title_relevance("Cooking with Herbs", "python")
        assert score == 0.0

    def test_partial_skill_match(self):
        # "go" token → "golang" token in title (startswith check)
        score = _title_relevance("Golang Tutorial for Beginners", "go")
        assert score > 0.0

    def test_multi_token_skill_partial(self):
        score = _title_relevance("Machine Learning with TensorFlow", "machine learning")
        assert score == 1.0

    def test_empty_skill(self):
        assert _title_relevance("Some Title", "") == 0.0


# ── _compute_stage2_score ────────────────────────────────────────────────────

class TestComputeStage2Score:
    def test_perfect_resource(self):
        resource = {
            "title": "Python Tutorial",
            "skill_addressed": "python",
            "source_trust": 1.0,
            "engagement_ratio": 1.0,
            "recency_score": 1.0,
        }
        score = _compute_stage2_score(resource)
        # title_relevance = 1.0 (python in title)
        # 0.20*1 + 0.30*1 + 0.25*1 + 0.25*1 = 1.0
        assert score == pytest.approx(1.0)

    def test_zero_resource(self):
        resource = {
            "title": "Cooking Show",
            "skill_addressed": "python",
            "source_trust": 0.0,
            "engagement_ratio": 0.0,
            "recency_score": 0.0,
        }
        score = _compute_stage2_score(resource)
        # title_relevance = 0.0 (no overlap), all others = 0
        assert score == pytest.approx(0.0)

    def test_weighted_sum_correctness(self):
        resource = {
            "title": "Python Tutorial",   # title_relevance = 1.0
            "skill_addressed": "python",
            "source_trust": 0.5,          # weight 0.20 → 0.10
            "engagement_ratio": 0.4,      # weight 0.25 → 0.10
            "recency_score": 0.8,         # weight 0.25 → 0.20
        }
        # tr=1.0 → 0.30*1.0 = 0.30; total = 0.10+0.30+0.10+0.20 = 0.70
        score = _compute_stage2_score(resource)
        assert score == pytest.approx(0.70)

    def test_missing_fields_default_to_zero(self):
        resource = {"title": "Unknown", "skill_addressed": "python"}
        score = _compute_stage2_score(resource)
        assert 0.0 <= score <= 1.0


# ── build_learning_path ──────────────────────────────────────────────────────

def _make_resource(skill: str, url: str, source_trust=0.8, engagement=0.8,
                   recency=0.8, source="YouTube", description="great tutorial"):
    return {
        "title": f"{skill} Tutorial",
        "source": source,
        "url": url,
        "skill_addressed": skill,
        "source_trust": source_trust,
        "engagement_ratio": engagement,
        "recency_score": recency,
        "description": description,
    }


def _tag_mock(resources):
    """Return a tag result that labels every resource as 'intermediate'."""
    return [
        {"resource_index": r["index"], "level": "intermediate", "justification": "test"}
        for r in resources
    ]


def _desc_mock(resources):
    """Return a description eval that gives every resource score 8."""
    return [
        {"resource_index": r["resource_index"], "relevance_score": 8, "reason": "good"}
        for r in resources
    ]


SKILL_GAPS = [{"skill": "python", "priority": "high", "category": "Programming Language"}]


@pytest.mark.asyncio
async def test_empty_resources_returns_empty():
    result, warnings = await build_learning_path([], SKILL_GAPS)
    assert result == []
    assert warnings == []


@pytest.mark.asyncio
async def test_deduplication_keeps_first_occurrence():
    """Two resources with the same YouTube video ID — only the first should survive."""
    resources = [
        _make_resource("python", "https://www.youtube.com/watch?v=abc123"),
        _make_resource("python", "https://www.youtube.com/watch?v=abc123"),
    ]
    with (
        patch("services.ranker.gemini_service.tag_resources", new=AsyncMock(side_effect=_tag_mock)),
        patch("services.ranker.gemini_service.evaluate_descriptions", new=AsyncMock(side_effect=_desc_mock)),
    ):
        result, _ = await build_learning_path(resources, SKILL_GAPS)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_score_threshold_drops_low_quality():
    """Resources that score below MIN_SCORE_THRESHOLD must be excluded."""
    low_resource = _make_resource(
        "python", "https://www.youtube.com/watch?v=low1",
        source_trust=0.0, engagement=0.0, recency=0.0
    )
    with (
        patch("services.ranker.gemini_service.tag_resources", new=AsyncMock(return_value=[
            {"resource_index": 0, "level": "intermediate", "justification": "test"}
        ])),
        patch("services.ranker.gemini_service.evaluate_descriptions", new=AsyncMock(return_value=[
            {"resource_index": 0, "relevance_score": 0, "reason": "irrelevant"}
        ])),
    ):
        result, _ = await build_learning_path([low_resource], SKILL_GAPS)
    # score will be ~0.0, well below 0.55
    assert result == []


@pytest.mark.asyncio
async def test_phd_level_caps_beginner_to_one():
    """PhD education level must allow at most 1 beginner resource."""
    resources = []
    for i in range(5):
        r = _make_resource("python", f"https://www.youtube.com/watch?v=beg{i}")
        r["title"] = "Python Introduction for Beginners"  # force beginner level
        resources.append(r)

    def tag_beginner(res):
        return [{"resource_index": r["index"], "level": "beginner", "justification": "t"}
                for r in res]

    def desc_good(res):
        return [{"resource_index": r["resource_index"], "relevance_score": 9, "reason": "ok"}
                for r in res]

    with (
        patch("services.ranker.gemini_service.tag_resources", new=AsyncMock(side_effect=tag_beginner)),
        patch("services.ranker.gemini_service.evaluate_descriptions", new=AsyncMock(side_effect=desc_good)),
    ):
        result, _ = await build_learning_path(resources, SKILL_GAPS, education_level="phd")

    beginner_count = sum(1 for r in result if r["level"] == "beginner")
    assert beginner_count <= 1


@pytest.mark.asyncio
async def test_gemini_failure_produces_warning():
    """When tag_resources raises, build_learning_path should include a warning."""
    resources = [_make_resource("python", "https://www.youtube.com/watch?v=x1")]

    with (
        patch("services.ranker.gemini_service.tag_resources",
              new=AsyncMock(side_effect=Exception("Gemini timeout"))),
        patch("services.ranker.gemini_service.evaluate_descriptions",
              new=AsyncMock(side_effect=Exception("quota exceeded"))),
    ):
        result, warnings = await build_learning_path(resources, SKILL_GAPS)

    assert len(warnings) == 2
    assert any("level" in w.lower() for w in warnings)
    assert any("relevance" in w.lower() or "scoring" in w.lower() for w in warnings)


@pytest.mark.asyncio
async def test_max_per_gap_limit():
    """No more than max_per_gap resources from the same skill in a given level bucket."""
    resources = []
    for i in range(5):
        resources.append(_make_resource(
            "python", f"https://www.youtube.com/watch?v=mid{i}",
            source_trust=0.9, engagement=0.9, recency=0.9,
        ))

    def tag_inter(res):
        return [{"resource_index": r["index"], "level": "intermediate", "justification": "t"}
                for r in res]

    def desc_high(res):
        return [{"resource_index": r["resource_index"], "relevance_score": 9, "reason": "ok"}
                for r in res]

    with (
        patch("services.ranker.gemini_service.tag_resources", new=AsyncMock(side_effect=tag_inter)),
        patch("services.ranker.gemini_service.evaluate_descriptions", new=AsyncMock(side_effect=desc_high)),
    ):
        result, _ = await build_learning_path(resources, SKILL_GAPS, max_per_gap=2)

    python_intermediate = [r for r in result if r["skill_addressed"] == "python"
                           and r["level"] == "intermediate"]
    assert len(python_intermediate) <= 2
