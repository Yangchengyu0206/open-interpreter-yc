"""
Web search skill using Tavily API.
Requires: pip install tavily-python
TAVILY_API_KEY must be set in .env or environment.
"""
import os


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using Tavily and return a formatted summary.

    Usage: web_search("最新 Python 3.13 新功能")
    """
    try:
        from tavily import TavilyClient
    except ImportError:
        return (
            "尚未安裝 tavily-python。\n"
            "請在 venv 執行: .venv\\Scripts\\pip install tavily-python"
        )

    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        return "缺少 TAVILY_API_KEY，請在 .env 加入 TAVILY_API_KEY=tvly-..."

    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, max_results=max_results)

    results = response.get("results", [])
    if not results:
        return f"搜尋「{query}」無結果。"

    lines = [f"## 搜尋結果：{query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "（無標題）")
        url = r.get("url", "")
        content = r.get("content", "").strip().replace("\n", " ")[:300]
        lines.append(f"**{i}. {title}**")
        lines.append(f"   {url}")
        lines.append(f"   {content}")
        lines.append("")
    return "\n".join(lines)


def web_search_with_answer(query: str) -> str:
    """
    使用 Tavily 搜尋並回傳 AI 整理後的答案（含來源）。

    Usage: web_search_with_answer("台灣今天天氣如何")
    """
    try:
        from tavily import TavilyClient
    except ImportError:
        return "尚未安裝 tavily-python，請執行: .venv\\Scripts\\pip install tavily-python"

    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        return "缺少 TAVILY_API_KEY。"

    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        search_depth="advanced",
        include_answer=True,
        max_results=5,
    )

    answer = response.get("answer", "")
    results = response.get("results", [])

    lines = []
    if answer:
        lines.append(f"**摘要答案：** {answer}\n")
    lines.append("**來源：**")
    for r in results:
        lines.append(f"- [{r.get('title', '')}]({r.get('url', '')})")

    return "\n".join(lines)
