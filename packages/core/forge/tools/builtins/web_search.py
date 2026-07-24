from __future__ import annotations

import urllib.parse

import httpx
from forge.core.logging import get_logger

logger = get_logger("forge.tools.builtins.web_search")

_DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"


async def web_search(query: str, max_results: int = 5) -> str:
    if not query or not query.strip():
        return "Error: query cannot be empty"

    params = {"q": query.strip()}
    logger.info("web search", query=query, max_results=max_results)

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.post(_DUCKDUCKGO_URL, data=params)
            response.raise_for_status()
    except httpx.TimeoutException:
        return "Error: search request timed out"
    except httpx.HTTPStatusError as e:
        return f"Error: search returned HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        return f"Error: search request failed: {e}"

    results = _parse_duckduckgo_results(response.text, max_results)
    if not results:
        return "No results found."

    output = []
    for i, r in enumerate(results, 1):
        output.append(f"{i}. {r['title']}")
        output.append(f"   URL: {r['url']}")
        output.append(f"   {r['snippet']}")
        output.append("")

    return "\n".join(output).strip()


def _parse_duckduckgo_results(html: str, max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    lines = html.split("\n")
    in_result = False
    current: dict[str, str] = {}

    for line in lines:
        if len(results) >= max_results:
            break

        if 'class="result__title"' in line or 'class="result__a"' in line:
            in_result = True
            current = {}

            import re

            url_match = re.search(r'href="([^"]+)"', line)
            if url_match:
                url = url_match.group(1)
                current["url"] = urllib.parse.unquote(url)

            title_match = re.search(r'class="[^"]*">(.*?)</a>', line)
            if title_match:
                current["title"] = title_match.group(1)
            else:
                title_match = re.search(r'<a[^>]*>(.*?)</a>', line)
                if title_match:
                    current["title"] = title_match.group(1)
                else:
                    current["title"] = ""

            current["snippet"] = ""

        if in_result and ('class="result__snippet"' in line or 'class="result__snippet"' in html):
            import re

            snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', line)
            if snippet_match:
                current["snippet"] = _strip_html(snippet_match.group(1))
                results.append(current)
                in_result = False
            elif '</div>' in line and 'snippet' in current.get("snippet", ""):
                pass
            elif "snippet" not in current:
                current["snippet"] = _strip_html(line)

    if in_result and current.get("title"):
        if "snippet" not in current or not current["snippet"]:
            current["snippet"] = ""
        if current not in results:
            results.append(current)

    return results


def _strip_html(text: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#x27;", "'")
    text = text.replace("&#x2F;", "/")
    return text.strip()
