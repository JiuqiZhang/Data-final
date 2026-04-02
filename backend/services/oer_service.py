import httpx

OER_API_URL = "https://oercommons.org/api/v1/resources/"

LEVEL_MAP = {
    "lower-primary": "beginner",
    "upper-primary": "beginner",
    "secondary-lower": "beginner",
    "secondary-upper": "intermediate",
    "post-secondary": "intermediate",
    "higher-ed": "intermediate",
    "vocational": "intermediate",
    "graduate": "advanced",
    "research": "advanced",
}


async def search_oer(skill: str, max_results: int = 3) -> list[dict]:
    """Search OER Commons for resources about `skill`."""
    params = {
        "q": skill,
        "f.levelGroup": "higher-ed",
        "page_size": max_results,
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(OER_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        # Fall back to broader query using first word of skill
        first_word = skill.split()[0]
        if first_word == skill:
            return []
        params["q"] = first_word
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(OER_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

    results = []
    for item in data.get("results", []):
        raw_level = item.get("educationalLevel") or item.get("level") or ""
        level_hint = LEVEL_MAP.get(raw_level, None)
        results.append({
            "title": item.get("title", ""),
            "source": "OER Commons",
            "url": item.get("url") or f"https://oercommons.org/courses/{item.get('id', '')}",
            "source_trust": 0.8,
            "level_hint": level_hint,
        })

    return results
