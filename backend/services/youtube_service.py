import os
import re
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

# Channels known for high-quality educational content
EDU_CHANNELS = {
    "mit opencourseware", "stanford", "freecodecamp", "3blue1brown",
    "sentdex", "statquest", "andrej karpathy", "two minute papers",
    "google developers", "tensorflow", "pytorch", "deeplearning.ai",
    "krish naik", "codebasics", "data school", "ken jee",
}

# Hard pre-filter thresholds
MIN_DURATION_SECONDS = 180   # 3 minutes
MAX_AGE_YEARS = 3
MIN_VIEWS = 1_000

# Skills whose names are common English words — map to unambiguous search terms
_SKILL_QUERY_OVERRIDES: dict[str, str] = {
    "go":     "Golang programming language",
    "r":      "R programming language statistics",
    "c":      "C programming language",
    "rust":   "Rust programming language systems",
    "swift":  "Swift iOS programming",
    "julia":  "Julia programming language data science",
    "scala":  "Scala programming language",
}

# Generic words that appear in queries but shouldn't count as "content" keywords
_QUERY_STOPWORDS = frozenset({
    "tutorial", "course", "learn", "guide", "skills", "professional",
    "development", "programming", "language", "introduction", "beginner",
    "for", "and", "the", "in", "a",
})

# Regex to detect titles that are explicitly in a non-English language
_NON_ENGLISH_PATTERN = re.compile(
    r'\|\s*(?:hindi|malayalam|tamil|telugu|kannada|bengali|urdu|arabic|español|'
    r'français|deutsch|português|italiano|türkçe|punjabi|gujarati|marathi|'
    r'sinhala|thai|vietnamese|indonesia|bahasa)\b'
    r'|'
    r'\bin\s+(?:hindi|malayalam|tamil|telugu|kannada|bengali|urdu|arabic|español|'
    r'français|deutsch|português|italiano|türkçe|punjabi|gujarati|marathi)\b',
    re.IGNORECASE,
)


def _is_likely_english(title: str) -> bool:
    """Return False if the title is clearly in a non-English language."""
    # Non-Latin Unicode letters → non-English script
    if any(ord(c) > 0x024F for c in title if c.isalpha()):
        return False
    # Explicit "in <language>" or "| <language>" marker
    if _NON_ENGLISH_PATTERN.search(title):
        return False
    return True


def _build_query(skill: str, category: str = "", advanced: bool = False) -> str:
    """Return an unambiguous YouTube search query for the given skill + category."""
    override = _SKILL_QUERY_OVERRIDES.get(skill.lower())
    base = override if override else skill
    if advanced:
        if category == "Soft Skill":
            return f"{skill} advanced professional strategies leadership"
        return f"{base} advanced best practices production"
    if override:
        return f"{base} tutorial"
    if category == "Soft Skill":
        return f"{skill} professional development skills"
    if category == "Programming Language":
        return f"{skill} programming tutorial"
    return f"{skill} tutorial"


def _content_keywords(skill: str, category: str = "") -> set[str]:
    """
    Return the meaningful content keywords used to verify title overlap.
    Uses the disambiguated form (e.g. 'golang' for skill 'Go') so that
    common English words don't produce false positives.
    """
    override = _SKILL_QUERY_OVERRIDES.get(skill.lower())
    if override:
        tokens = set(override.lower().split()) - _QUERY_STOPWORDS
        if tokens:
            return tokens
    return set(skill.lower().split()) - _QUERY_STOPWORDS or {skill.lower()}


def _source_trust(channel_title: str) -> float:
    lower = channel_title.lower()
    for edu in EDU_CHANNELS:
        if edu in lower:
            return 1.0
    return 0.5


def _parse_duration_seconds(duration: str) -> int:
    """Parse ISO 8601 duration (e.g. PT1H5M30S) to total seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match:
        return 0
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 3600 + m * 60 + s


def _engagement_ratio(view_count: int, like_count: int) -> float:
    """Normalize likes/views to 0–1. 5% engagement rate = 1.0."""
    if view_count == 0:
        return 0.0
    return min((like_count / view_count) / 0.05, 1.0)


def _recency_score(published_at: str) -> float:
    """Linear decay over 3 years: 0 years old = 1.0, 3 years old = 0.0."""
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_years = (datetime.now(timezone.utc) - pub).days / 365.25
        return max(0.0, 1.0 - age_years / 3.0)
    except Exception:
        return 0.5


def _has_keyword_overlap(title: str, keywords: set[str]) -> bool:
    """Return True if any content keyword appears in the title."""
    title_tokens = set(re.split(r"\W+", title.lower()))
    return bool(keywords & title_tokens)


def _passes_prefilter(title: str, keywords: set[str], duration_seconds: int,
                      published_at: str, view_count: int) -> bool:
    if not _is_likely_english(title):
        return False
    if duration_seconds < MIN_DURATION_SECONDS:
        return False
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_years = (datetime.now(timezone.utc) - pub).days / 365.25
        if age_years > MAX_AGE_YEARS:
            return False
    except Exception:
        pass
    if view_count < MIN_VIEWS:
        return False
    if not _has_keyword_overlap(title, keywords):
        return False
    return True


async def search_youtube(
    skill: str, category: str = "", max_results: int = 8, advanced: bool = False
) -> list[dict]:
    """
    Two-step fetch: search for video IDs, then fetch full details.
    Applies hard pre-filters before returning enriched resource dicts.
    category is used to build a more specific, unambiguous query.
    Set advanced=True to fetch advanced-level content for the skill.
    """
    if not YOUTUBE_API_KEY:
        return []

    query = _build_query(skill, category, advanced=advanced)
    keywords = _content_keywords(skill, category)

    # Step 1 — search, retrieve only IDs
    search_params = {
        "part": "id",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "relevanceLanguage": "en",
        "safeSearch": "strict",
        "key": YOUTUBE_API_KEY,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(YOUTUBE_SEARCH_URL, params=search_params)
        resp.raise_for_status()
        search_data = resp.json()

    video_ids = [
        item["id"]["videoId"]
        for item in search_data.get("items", [])
        if item.get("id", {}).get("videoId")
    ]
    if not video_ids:
        return []

    # Step 2 — fetch snippet + statistics + contentDetails in one call
    videos_params = {
        "part": "snippet,statistics,contentDetails",
        "id": ",".join(video_ids),
        "key": YOUTUBE_API_KEY,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(YOUTUBE_VIDEOS_URL, params=videos_params)
        resp.raise_for_status()
        videos_data = resp.json()

    results = []
    for item in videos_data.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})

        video_id = item["id"]
        title = snippet.get("title", "")
        channel_title = snippet.get("channelTitle", "")
        published_at = snippet.get("publishedAt", "")
        description = snippet.get("description", "")

        view_count = int(stats.get("viewCount", 0))
        like_count = int(stats.get("likeCount", 0))
        duration_seconds = _parse_duration_seconds(content.get("duration", ""))

        if not _passes_prefilter(title, keywords, duration_seconds, published_at, view_count):
            continue

        results.append({
            "title": title,
            "source": "YouTube",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "channel_title": channel_title,
            "source_trust": _source_trust(channel_title),
            "view_count": view_count,
            "like_count": like_count,
            "duration_seconds": duration_seconds,
            "engagement_ratio": _engagement_ratio(view_count, like_count),
            "recency_score": _recency_score(published_at),
            "description": description,
        })

    return results
