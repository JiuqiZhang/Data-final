import asyncio
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import httpx

WIKIVERSITY_API_URL = "https://en.wikiversity.org/w/api.php"
WIKIVERSITY_PAGEVIEWS_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
WIKIVERSITY_UA = "SkillArchitect/1.0 (educational skill-gap finder; https://github.com/skill-architect)"

# Normalisation cap: 3000 total views over 3 months ≈ 1.0 engagement
_PAGEVIEW_NORM_CAP = 3000

# Same disambiguation table as youtube_service — maps ambiguous skill names to
# unambiguous search terms so e.g. "Go" doesn't match "Should we go vegan?"
_SKILL_SEARCH_OVERRIDES: dict[str, str] = {
    "go":    "Golang programming language",
    "r":     "R programming language statistics",
    "c":     "C programming language",
    "rust":  "Rust programming language systems",
    "swift": "Swift iOS programming",
    "julia": "Julia programming language",
    "scala": "Scala programming language",
}


def _build_oer_query(skill: str) -> str:
    return _SKILL_SEARCH_OVERRIDES.get(skill.lower(), skill)


def _recency_score(timestamp: str) -> float:
    """Linear decay over 3 years from last edit timestamp."""
    try:
        edited = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        age_years = (datetime.now(timezone.utc) - edited).days / 365.25
        return max(0.0, 1.0 - age_years / 3.0)
    except Exception:
        return 0.5


def _engagement_ratio(total_views: int) -> float:
    """Normalise 3-month total page views to 0–1. Cap at 3000 views = 1.0."""
    return min(total_views / _PAGEVIEW_NORM_CAP, 1.0)


def _pageview_date_range() -> tuple[str, str]:
    """Return (start, end) in YYYYMMDD format covering the last 3 complete months."""
    now = datetime.now(timezone.utc)
    end = now.replace(day=1)
    start = (end - timedelta(days=90)).replace(day=1)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


async def _fetch_pageviews(client: httpx.AsyncClient, title: str) -> int:
    """Fetch total page views for a Wikiversity article over the last 3 months."""
    start, end = _pageview_date_range()
    encoded_title = quote(title.replace(" ", "_"), safe="")
    url = (
        f"{WIKIVERSITY_PAGEVIEWS_URL}/en.wikiversity/all-access/all-agents"
        f"/{encoded_title}/monthly/{start}/{end}"
    )
    try:
        resp = await client.get(url, headers={"User-Agent": WIKIVERSITY_UA})
        if resp.status_code != 200:
            return 0
        data = resp.json()
        return sum(item.get("views", 0) for item in data.get("items", []))
    except Exception:
        return 0


async def search_oer(skill: str, max_results: int = 3) -> list[dict]:
    """
    Three-step fetch:
      1. Search Wikiversity for relevant pages.
      2. Batch-fetch last revision timestamp (recency signal).
      3. Concurrent pageviews fetch per article (engagement signal).
    """
    query = _build_oer_query(skill)

    # Step 1 — search
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": 0,
        "srlimit": max_results,
        "format": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": WIKIVERSITY_UA}) as client:
            resp = await client.get(WIKIVERSITY_API_URL, params=search_params)
            resp.raise_for_status()
            search_data = resp.json()
    except Exception:
        return []

    pages = [
        item for item in search_data.get("query", {}).get("search", [])
        if item.get("title")
    ]
    if not pages:
        return []

    titles = [p["title"] for p in pages]

    # Step 2 — batch-fetch last revision timestamp
    details_params = {
        "action": "query",
        "prop": "revisions",
        "titles": "|".join(titles),
        "rvprop": "timestamp",
        "rvlimit": 1,
        "format": "json",
    }
    revision_map: dict[str, str] = {}  # title → last edit timestamp
    try:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": WIKIVERSITY_UA}) as client:
            resp = await client.get(WIKIVERSITY_API_URL, params=details_params)
            resp.raise_for_status()
            details_data = resp.json()
        for page in details_data.get("query", {}).get("pages", {}).values():
            t = page.get("title", "")
            revisions = page.get("revisions", [])
            if revisions:
                revision_map[t] = revisions[0].get("timestamp", "")
    except Exception:
        pass

    # Step 3 — concurrent pageviews fetch
    async with httpx.AsyncClient(timeout=15.0) as client:
        view_results = await asyncio.gather(
            *[_fetch_pageviews(client, t) for t in titles],
            return_exceptions=True,
        )

    results = []
    for i, title in enumerate(titles):
        # Skip pages whose titles contain non-Latin Unicode (non-English content)
        if any(ord(c) > 0x024F for c in title if c.isalpha()):
            continue

        url_title = title.replace(" ", "_")
        last_edited = revision_map.get(title, "")
        views = view_results[i] if isinstance(view_results[i], int) else 0

        results.append({
            "title": title,
            "source": "Wikiversity",
            "url": f"https://en.wikiversity.org/wiki/{url_title}",
            "source_trust": 0.85,
            "recency_score": _recency_score(last_edited),
            "engagement_ratio": _engagement_ratio(views),
        })

    return results
