import os
from typing import List, Dict
import aiohttp

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

async def serper_scholar_search(query: str, max_results: int = 6, timeout_seconds: int = 12, gl: str = "vn", hl: str = "vi") -> List[Dict[str, str]]:
    """Call Serper.dev Scholar API and normalize results to {title,url,snippet}."""
    if not SERPER_API_KEY:
        return []

    url = "https://google.serper.dev/scholar"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "gl": gl,
        "hl": hl,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=timeout_seconds) as resp:
                data = await resp.json(content_type=None)
        except Exception:
            return []

    results: List[Dict[str, str]] = []
    organic = data.get("organic") or []
    for item in organic:
        title = item.get("title") or item.get("name") or ""
        url = item.get("link") or item.get("url") or ""
        snippet = item.get("snippet") or item.get("description") or item.get("abstract") or ""
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


