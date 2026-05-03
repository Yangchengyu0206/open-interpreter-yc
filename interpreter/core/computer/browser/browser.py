import os
import threading
import time

import html2text
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
_REQUEST_TIMEOUT_SEC = 60


def _tavily_api_key(computer) -> str:
    key = getattr(computer, "tavily_api_key", None)
    return (key or os.getenv("TAVILY_API_KEY") or "").strip()


def _parse_tavily_error(response: requests.Response) -> str:
    try:
        data = response.json()
        detail = data.get("detail")
        if isinstance(detail, dict) and detail.get("error"):
            return str(detail["error"])
        if detail:
            return str(detail)
        return str(data)
    except Exception:
        return response.text or response.reason or "Unknown error"


class Browser:
    def __init__(self, computer):
        self.computer = computer
        self._driver = None

    @property
    def driver(self, headless=False):
        if self._driver is None:
            self.setup(headless)
        return self._driver

    @driver.setter
    def driver(self, value):
        self._driver = value

    def _search_open_interpreter(self, query):
        response = requests.get(
            f'{self.computer.api_base.strip("/")}/browser/search',
            params={"query": query},
            timeout=_REQUEST_TIMEOUT_SEC,
        )
        response.raise_for_status()
        return response.json()["result"]

    def _tavily_settings(self):
        depth = getattr(self.computer, "tavily_search_depth", None) or os.getenv(
            "TAVILY_SEARCH_DEPTH", "basic"
        )
        mr = getattr(self.computer, "tavily_max_results", None)
        if mr is None:
            try:
                mr = int(os.getenv("TAVILY_MAX_RESULTS", "8"))
            except ValueError:
                mr = 8
        mr = max(1, min(20, int(mr)))
        include_answer = getattr(self.computer, "tavily_include_answer", None)
        if include_answer is None:
            include_answer = os.getenv("TAVILY_INCLUDE_ANSWER", "true").lower() in (
                "1",
                "true",
                "yes",
            )
        return depth, mr, include_answer

    def _format_tavily_response(self, data: dict) -> str:
        parts = []
        answer = data.get("answer")
        if isinstance(answer, str) and answer.strip():
            parts.append(f"### Answer\n\n{answer.strip()}")

        results = data.get("results") or []
        if results:
            parts.append("\n### Sources")
            for i, r in enumerate(results, start=1):
                title = (r.get("title") or "").strip() or "(no title)"
                url = (r.get("url") or "").strip()
                content = (r.get("content") or "").strip()
                lines = [f"\n{i}. **{title}**"]
                if url:
                    lines.append(f"   {url}")
                if content:
                    lines.append(f"\n   {content}")
                parts.append("\n".join(lines))

        out = "\n".join(parts).strip()
        return out if out else str(data)

    def search(self, query):
        """
        Searches the web for the specified query.

        When ``TAVILY_API_KEY`` (env) or ``computer.tavily_api_key`` is set,
        calls `Tavily Search <https://api.tavily.com/search>`.
        Otherwise falls back to ``computer.api_base`` ``/browser/search``
        (Open Interpreter hosted endpoint).
        """
        api_key = _tavily_api_key(self.computer)
        if api_key:
            return self._search_tavily(query, api_key)
        return self._search_open_interpreter(query)

    def _search_tavily(self, query, api_key):
        depth, max_results, include_answer = self._tavily_settings()
        payload = {
            "query": query,
            "search_depth": depth,
            "max_results": max_results,
            "include_answer": include_answer,
        }
        response = requests.post(
            TAVILY_SEARCH_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=_REQUEST_TIMEOUT_SEC,
        )
        if not response.ok:
            raise RuntimeError(
                f"Tavily Search failed ({response.status_code}): {_parse_tavily_error(response)}"
            )
        return self._format_tavily_response(response.json())

    def fast_search(self, query):
        """
        Searches the web for the specified query.

        Uses Tavily when configured (same as ``search``). Otherwise preserves
        the legacy behavior (parallel ``/browser/search`` + scripted browser).
        """
        api_key = _tavily_api_key(self.computer)
        if api_key:
            return self._search_tavily(query, api_key)

        # Start the request in a separate thread
        response_thread = threading.Thread(
            target=lambda: setattr(
                threading.current_thread(),
                "response",
                requests.get(
                    f'{self.computer.api_base.strip("/")}/browser/search',
                    params={"query": query},
                    timeout=_REQUEST_TIMEOUT_SEC,
                ),
            )
        )
        response_thread.start()

        # Perform the Google search
        self.search_google(query, delays=False)

        # Wait for the request to complete and get the result
        response_thread.join()
        response = response_thread.response
        response.raise_for_status()
        return response.json()["result"]

    def setup(self, headless):
        try:
            self.service = Service(ChromeDriverManager().install())
            self.options = webdriver.ChromeOptions()
            # Run Chrome in headless mode
            if headless:
                self.options.add_argument("--headless")
                self.options.add_argument("--disable-gpu")
                self.options.add_argument("--no-sandbox")
            self._driver = webdriver.Chrome(service=self.service, options=self.options)
        except Exception as e:
            print(f"An error occurred while setting up the WebDriver: {e}")
            self._driver = None

    def go_to_url(self, url):
        """Navigate to a URL"""
        self.driver.get(url)
        time.sleep(1)

    def search_google(self, query, delays=True):
        """Perform a Google search"""
        self.driver.get("https://www.perplexity.ai")
        # search_box = self.driver.find_element(By.NAME, 'q')
        # search_box.send_keys(query)
        # search_box.send_keys(Keys.RETURN)
        body = self.driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.COMMAND + "k")
        time.sleep(0.5)
        active_element = self.driver.switch_to.active_element
        active_element.send_keys(query)
        active_element.send_keys(Keys.RETURN)
        if delays:
            time.sleep(3)

    def analyze_page(self, intent):
        """Extract HTML, list interactive elements, and analyze with AI"""
        html_content = self.driver.page_source
        text_content = html2text.html2text(html_content)

        # text_content = text_content[:len(text_content)//2]

        elements = (
            self.driver.find_elements(By.TAG_NAME, "a")
            + self.driver.find_elements(By.TAG_NAME, "button")
            + self.driver.find_elements(By.TAG_NAME, "input")
            + self.driver.find_elements(By.TAG_NAME, "select")
        )

        elements_info = [
            {
                "id": idx,
                "text": elem.text,
                "attributes": elem.get_attribute("outerHTML"),
            }
            for idx, elem in enumerate(elements)
        ]

        ai_query = f"""
        Below is the content of the current webpage along with interactive elements. 
        Given the intent "{intent}", please extract useful information and provide sufficient details 
        about interactive elements, focusing especially on those pertinent to the provided intent.
        
        If the information requested by the intent "{intent}" is present on the page, simply return that.

        If not, return the top 10 most relevant interactive elements in a concise, actionable format, listing them on separate lines
        with their ID, a description, and their possible action.

        Do not hallucinate.

        Page Content:
        {text_content}
        
        Interactive Elements:
        {elements_info}
        """

        # response = self.computer.ai.chat(ai_query)

        # screenshot = self.driver.get_screenshot_as_base64()
        # old_model = self.computer.interpreter.llm.model
        # self.computer.interpreter.llm.model = "gpt-4o-mini"
        # response = self.computer.ai.chat(ai_query, base64=screenshot)
        # self.computer.interpreter.llm.model = old_model

        old_model = self.computer.interpreter.llm.model
        self.computer.interpreter.llm.model = "gpt-4o-mini"
        response = self.computer.ai.chat(ai_query)
        self.computer.interpreter.llm.model = old_model

        print(response)
        print(
            "Please now utilize this information or interact with the interactive elements provided to answer the user's query."
        )

    def quit(self):
        """Close the browser"""
        self.driver.quit()
