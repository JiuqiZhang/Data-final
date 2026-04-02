import os
import httpx
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# Channels known for high-quality educational content
EDU_CHANNELS = {
    "mit opencourseware", "stanford", "freecodecamp", "3blue1brown",
    "sentdex", "statquest", "andrej karpathy", "two minute papers",
    "google developers", "tensorflow", "pytorch", "deeplearning.ai",
    "krish naik", "codebasics", "data school", "ken jee",
}


def _source_trust(channel_title: str) -> float:
    lower = channel_title.lower()
    for edu in EDU_CHANNELS:
        if edu in lower:
            return 1.0
    return 0.5


async def search_youtube(skill: str, max_results: int = 5) -> list[dict]:
    """Search YouTube for educational videos about `skill`."""
    if not YOUTUBE_API_KEY:
        return []

    query = f"{skill} tutorial"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "relevanceLanguage": "en",
        "safeSearch": "strict",
        "key": YOUTUBE_API_KEY,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(YOUTUBE_SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("items", []):
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId", "")
        if not video_id:
            continue
        channel_title = snippet.get("channelTitle", "")
        results.append({
            "title": snippet.get("title", ""),
            "source": "YouTube",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "channel_title": channel_title,
            "source_trust": _source_trust(channel_title),
        })

    return results
