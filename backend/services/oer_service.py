import httpx

WIKIVERSITY_API_URL = "https://en.wikiversity.org/w/api.php"
WIKIVERSITY_UA = "SkillArchitect/1.0 (educational skill-gap finder; https://github.com/skill-architect)"

async def search_oer(skill: str, max_results: int = 3) -> list[dict]:
    """Search Wikiversity for open educational resources about `skill`."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": skill,
        "srnamespace": 0,
        "srlimit": max_results,
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": WIKIVERSITY_UA}) as client:
            resp = await client.get(WIKIVERSITY_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    results = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        if not title:
            continue
        url_title = title.replace(" ", "_")
        results.append({
            "title": title,
            "source": "Wikiversity",
            "url": f"https://en.wikiversity.org/wiki/{url_title}",
            "source_trust": 0.85,
        })

    return results
