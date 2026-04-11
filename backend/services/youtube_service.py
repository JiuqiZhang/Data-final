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


def _has_keyword_overlap(title: str, skill: str) -> bool:
    skill_tokens = set(skill.lower().split())
    title_tokens = set(title.lower().split())
    return bool(skill_tokens & title_tokens)


def _passes_prefilter(title: str, skill: str, duration_seconds: int,
                      published_at: str, view_count: int) -> bool:
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
    if not _has_keyword_overlap(title, skill):
        return False
    return True


async def search_youtube(skill: str, max_results: int = 8) -> list[dict]:
    """
    Two-step fetch: search for video IDs, then fetch full details.
    Applies hard pre-filters before returning enriched resource dicts.
    """
    if not YOUTUBE_API_KEY:
        return []

    # Step 1 — search, retrieve only IDs
    search_params = {
        "part": "id",
        "q": f"{skill} tutorial",
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

        if not _passes_prefilter(title, skill, duration_seconds, published_at, view_count):
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
