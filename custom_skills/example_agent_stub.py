# 此檔案會與其他 custom_skills/*.py 一起被合併載入到同一個 Python 直譯器環境。
# 在此實作你自己的 LangChain / LangGraph，並以「函式」暴露給模型呼叫。


def example_echo_agent(user_text: str) -> str:
    """範例：之後可改成呼叫你的 Graph / Chain。"""
    return f"[example_echo_agent] {user_text}"


def run_langgraph_task(user_text: str) -> str:
    """
    範本：有安裝 langgraph / langchain 時再啟用實作。
    venv 內請先: pip install langchain langgraph （依你實際套件為準）
    """
    try:
        import langgraph  # noqa: F401
    except ImportError:
        return (
            "尚未安裝 LangGraph/LangChain。"
            "請在專案 venv 執行: pip install langchain langgraph"
        )
    return "尚未實作 Graph，請編輯 custom_skills/example_agent_stub.py"
