"""Tests for gemini_service.py — JSON parsing and response structure validation."""
import json
import pytest

from services.gemini_service import _parse_json


# ── _parse_json ───────────────────────────────────────────────────────────────

class TestParseJson:
    def test_plain_json_object(self):
        result = _parse_json('{"skill": "python", "level": "beginner"}')
        assert result == {"skill": "python", "level": "beginner"}

    def test_plain_json_array(self):
        result = _parse_json('[{"resource_index": 0, "level": "intermediate"}]')
        assert result == [{"resource_index": 0, "level": "intermediate"}]

    def test_markdown_fenced_json(self):
        raw = "```json\n{\"key\": \"value\"}\n```"
        assert _parse_json(raw) == {"key": "value"}

    def test_markdown_fence_without_language(self):
        raw = "```\n[1, 2, 3]\n```"
        assert _parse_json(raw) == [1, 2, 3]

    def test_leading_trailing_whitespace(self):
        assert _parse_json('  {"x": 1}  ') == {"x": 1}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json("not valid json")

    def test_nested_structure(self):
        raw = json.dumps({
            "skill_gaps": [{"skill": "SQL", "priority": "high", "category": "Database"}],
            "education_level": "master",
        })
        result = _parse_json(raw)
        assert result["education_level"] == "master"
        assert result["skill_gaps"][0]["skill"] == "SQL"


# ── extract_skill_gaps output contract ───────────────────────────────────────
# These tests validate that real Gemini output (captured as fixtures) conforms
# to the expected schema — add sample JSON strings here as you collect them.

SAMPLE_EXTRACTION = {
    "resume_skills": ["Python", "SQL"],
    "jd_skills": ["Python", "SQL", "Spark", "Kubernetes"],
    "skill_gaps": [
        {"skill": "Spark", "category": "Big Data", "priority": "high"},
        {"skill": "Kubernetes", "category": "Cloud/DevOps", "priority": "medium"},
    ],
    "education_level": "bachelor",
}

SAMPLE_TAG_RESULT = [
    {"resource_index": 0, "level": "beginner", "justification": "Covers Spark basics."},
    {"resource_index": 1, "level": "advanced", "justification": "Production Spark tuning."},
]

SAMPLE_DESC_RESULT = [
    {"resource_index": 0, "relevance_score": 8, "reason": "Directly teaches Spark."},
    {"resource_index": 1, "relevance_score": 3, "reason": "Unrelated cooking content."},
]


class TestExtractionSchema:
    def test_required_keys_present(self):
        for key in ("resume_skills", "jd_skills", "skill_gaps", "education_level"):
            assert key in SAMPLE_EXTRACTION

    def test_education_level_valid(self):
        assert SAMPLE_EXTRACTION["education_level"] in ("bachelor", "master", "phd")

    def test_skill_gap_fields(self):
        for gap in SAMPLE_EXTRACTION["skill_gaps"]:
            assert "skill" in gap
            assert gap["priority"] in ("high", "medium", "low")


class TestTagResultSchema:
    def test_level_values_valid(self):
        valid_levels = {"beginner", "intermediate", "advanced"}
        for item in SAMPLE_TAG_RESULT:
            assert "resource_index" in item
            assert item["level"] in valid_levels
            assert "justification" in item


class TestDescResultSchema:
    def test_score_range(self):
        for item in SAMPLE_DESC_RESULT:
            assert "resource_index" in item
            assert 0 <= item["relevance_score"] <= 10
            assert "reason" in item
