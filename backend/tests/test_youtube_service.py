"""Tests for youtube_service.py — query building, pre-filtering, scoring, and TTL cache."""
import time
import pytest

from services.youtube_service import (
    _build_query,
    _parse_duration_seconds,
    _passes_prefilter,
    _source_trust,
    _is_likely_english,
    _engagement_ratio,
    _TTLCache,
)


# ── _build_query ─────────────────────────────────────────────────────────────

class TestBuildQuery:
    def test_override_skill(self):
        assert _build_query("go") == "Golang programming language tutorial"
        assert _build_query("r") == "R programming language statistics tutorial"
        assert _build_query("rust") == "Rust programming language systems tutorial"

    def test_override_case_insensitive(self):
        assert _build_query("Go") == "Golang programming language tutorial"

    def test_programming_language_category(self):
        query = _build_query("scala", category="Programming Language")
        assert "scala" in query.lower()
        assert "tutorial" in query.lower()

    def test_soft_skill(self):
        query = _build_query("communication", category="Soft Skill")
        assert "communication" in query.lower()
        assert "professional" in query.lower()

    def test_advanced_flag_standard(self):
        query = _build_query("python", advanced=True)
        assert "advanced" in query.lower() or "best practices" in query.lower() or "production" in query.lower()

    def test_advanced_flag_soft_skill(self):
        query = _build_query("teamwork", category="Soft Skill", advanced=True)
        assert "advanced" in query.lower() or "leadership" in query.lower()

    def test_regular_skill(self):
        query = _build_query("pytorch")
        assert "pytorch" in query.lower()


# ── _parse_duration_seconds ───────────────────────────────────────────────────

class TestParseDurationSeconds:
    def test_hours_minutes_seconds(self):
        assert _parse_duration_seconds("PT1H5M30S") == 3600 + 300 + 30

    def test_minutes_only(self):
        assert _parse_duration_seconds("PT45M") == 2700

    def test_seconds_only(self):
        assert _parse_duration_seconds("PT90S") == 90

    def test_hours_only(self):
        assert _parse_duration_seconds("PT2H") == 7200

    def test_empty_string(self):
        assert _parse_duration_seconds("") == 0

    def test_none_like_empty(self):
        assert _parse_duration_seconds(None) == 0


# ── _passes_prefilter ─────────────────────────────────────────────────────────

class TestPassesPrefilter:
    RECENT = "2024-06-01T00:00:00Z"   # within 3 years of 2026
    OLD    = "2020-01-01T00:00:00Z"   # > 3 years old
    KW     = {"python"}

    def test_all_good(self):
        assert _passes_prefilter("Python Tutorial", self.KW, 600, self.RECENT, 5000)

    def test_fails_non_english(self):
        assert not _passes_prefilter("Python Tutorial in Hindi", self.KW, 600, self.RECENT, 5000)

    def test_fails_too_short(self):
        assert not _passes_prefilter("Python Tutorial", self.KW, 60, self.RECENT, 5000)

    def test_fails_too_old(self):
        assert not _passes_prefilter("Python Tutorial", self.KW, 600, self.OLD, 5000)

    def test_fails_too_few_views(self):
        assert not _passes_prefilter("Python Tutorial", self.KW, 600, self.RECENT, 50)

    def test_fails_no_keyword_overlap(self):
        assert not _passes_prefilter("Cooking with Herbs", self.KW, 600, self.RECENT, 5000)

    def test_exact_min_duration_boundary(self):
        # 180 seconds is the minimum — should pass
        assert _passes_prefilter("Python Tutorial", self.KW, 180, self.RECENT, 5000)

    def test_below_min_duration_boundary(self):
        assert not _passes_prefilter("Python Tutorial", self.KW, 179, self.RECENT, 5000)


# ── _source_trust ────────────────────────────────────────────────────────────

class TestSourceTrust:
    def test_known_edu_channel(self):
        assert _source_trust("freeCodeCamp.org") == 1.0
        assert _source_trust("MIT OpenCourseWare") == 1.0
        assert _source_trust("3Blue1Brown") == 1.0

    def test_unknown_channel(self):
        assert _source_trust("Random Tech Channel") == 0.5

    def test_case_insensitive(self):
        assert _source_trust("FREECODECAMP") == 1.0


# ── _is_likely_english ───────────────────────────────────────────────────────

class TestIsLikelyEnglish:
    def test_english_title(self):
        assert _is_likely_english("Python Tutorial for Beginners")

    def test_non_latin_script(self):
        assert not _is_likely_english("Python 教程 for Beginners")

    def test_explicit_hindi_marker(self):
        assert not _is_likely_english("Python Tutorial in Hindi")

    def test_pipe_language_marker(self):
        assert not _is_likely_english("Learn Python | Hindi")

    def test_mixed_latin_accents_ok(self):
        # Extended Latin (accents) should still pass
        assert _is_likely_english("Résumé Writing Tips")


# ── _engagement_ratio ────────────────────────────────────────────────────────

class TestEngagementRatio:
    def test_five_percent_returns_one(self):
        # 5% engagement = 1.0
        assert _engagement_ratio(1000, 50) == pytest.approx(1.0)

    def test_caps_at_one(self):
        # Above 5% caps at 1.0
        assert _engagement_ratio(100, 20) == pytest.approx(1.0)

    def test_zero_views(self):
        assert _engagement_ratio(0, 0) == 0.0

    def test_proportional(self):
        # 2.5% engagement = 0.5
        assert _engagement_ratio(1000, 25) == pytest.approx(0.5)


# ── _TTLCache ────────────────────────────────────────────────────────────────

class TestTTLCache:
    def test_miss_before_set(self):
        cache = _TTLCache(maxsize=10, ttl=60)
        assert cache.get("missing") is None

    def test_hit_after_set(self):
        cache = _TTLCache(maxsize=10, ttl=60)
        cache.set("k", [1, 2, 3])
        assert cache.get("k") == [1, 2, 3]

    def test_expiry(self):
        cache = _TTLCache(maxsize=10, ttl=0.01)  # 10 ms TTL
        cache.set("k", "value")
        time.sleep(0.02)
        assert cache.get("k") is None

    def test_lru_eviction(self):
        cache = _TTLCache(maxsize=3, ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Access "a" to make it recently used
        cache.get("a")
        # Adding "d" should evict "b" (oldest not recently accessed)
        cache.set("d", 4)
        assert cache.get("b") is None
        assert cache.get("a") == 1
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_overwrite_updates_expiry(self):
        cache = _TTLCache(maxsize=10, ttl=60)
        cache.set("k", "old")
        cache.set("k", "new")
        assert cache.get("k") == "new"
