import inspect
import json

from .ai.ai import Ai
from .browser.browser import Browser
from .calendar.calendar import Calendar
from .clipboard.clipboard import Clipboard
from .contacts.contacts import Contacts
from .display.display import Display
from .docs.docs import Docs
from .files.files import Files
from .keyboard.keyboard import Keyboard
from .mail.mail import Mail
from .mouse.mouse import Mouse
from .os.os import Os
from .skills.skills import Skills
from .sms.sms import SMS
from .terminal.terminal import Terminal
from .vision.vision import Vision


class Computer:
    def __init__(self, interpreter):
        self.interpreter = interpreter

        self.terminal = Terminal(self)

        self.offline = False
        self.verbose = False
        self.debug = False

        self.mouse = Mouse(self)
        self.keyboard = Keyboard(self)
        self.display = Display(self)
        self.clipboard = Clipboard(self)
        self.mail = Mail(self)
        self.sms = SMS(self)
        self.calendar = Calendar(self)
        self.contacts = Contacts(self)
        self.browser = Browser(self)
        self.os = Os(self)
        self.vision = Vision(self)
        self.skills = Skills(self)
        self.docs = Docs(self)
        self.ai = Ai(self)
        self.files = Files(self)

        self.emit_images = True
        self.api_base = "https://api.openinterpreter.com/v0"
        self.save_skills = True

        # 預設為 False
        self.import_computer_api = False  # Defaults to false
        # 因為我們只想執行一次
        self._has_imported_computer_api = False  # Because we only want to do this once

        self.import_skills = False
        self._has_imported_skills = False
        self.max_output = (
            self.interpreter.max_output
        # 應與 interpreter.max_output 保持一致
        )  # Should mirror interpreter.max_output

        computer_tools = "\n".join(
            self._get_all_computer_tools_signature_and_description()
        )

        self.system_message = f"""

# THE COMPUTER API

A python `computer` module is ALREADY IMPORTED, and can be used for many tasks:

```python
{computer_tools}
```

Do not import the computer module, or any of its sub-modules. They are already imported.

    """.strip()

    # computer.terminal.languages 的捷徑屬性
    # Shortcut for computer.terminal.languages
    @property
    def languages(self):
        return self.terminal.languages

    @languages.setter
    def languages(self, value):
        self.terminal.languages = value

    def _get_all_computer_tools_list(self):
        return [
            self.mouse,
            self.keyboard,
            self.display,
            self.clipboard,
            self.mail,
            self.sms,
            self.calendar,
            self.contacts,
            self.browser,
            self.os,
            self.vision,
            self.skills,
            self.docs,
            self.ai,
            self.files,
        ]

    def _get_all_computer_tools_signature_and_description(self):
        """
        This function returns a list of all the computer tools that are available with their signature and description from the function docstrings.
        for example:
        computer.browser.search(query) # Searches the web for the specified query and returns the results.
        computer.calendar.create_event(title: str, start_date: datetime.datetime, end_date: datetime.datetime, location: str = "", notes: str = "", calendar: str = None) -> str # Creates a new calendar event in the default calendar with the given parameters using AppleScript.
        """
        tools = self._get_all_computer_tools_list()
        tools_signature_and_description = []
        for tool in tools:
            tool_info = self._extract_tool_info(tool)
            for method in tool_info["methods"]:
                # 格式化為 工具簽名 # 工具描述
                # Format as tool_signature # tool_description
                formatted_info = f"{method['signature']} # {method['description']}"
                tools_signature_and_description.append(formatted_info)
        return tools_signature_and_description

    def _extract_tool_info(self, tool):
        """
        Helper function to extract the signature and description of a tool's methods.
        """
        tool_info = {"signature": tool.__class__.__name__, "methods": []}
        if tool.__class__.__name__ == "Browser":
            methods = []
            for name in dir(tool):
                if "driver" in name:
                    # 跳過名稱中包含 'driver' 的方法
                    continue  # Skip methods containing 'driver' in their name
                attr = getattr(tool, name)
                if (
                    callable(attr)
                    and not name.startswith("_")
                    and not hasattr(attr, "__wrapped__")
                    and not isinstance(attr, property)
                ):
                    # 手動構建方法簽名
                    # Construct the method signature manually
                    param_str = ", ".join(
                        param
                        for param in attr.__code__.co_varnames[
                            : attr.__code__.co_argcount
                        ]
                    )
                    full_signature = f"computer.{tool.__class__.__name__.lower()}.{name}({param_str})"
                    # 取得方法描述
                    # Get the method description
                    method_description = attr.__doc__ or ""
                    # 附加方法詳細資訊
                    # Append the method details
                    tool_info["methods"].append(
                        {
                            "signature": full_signature,
                            "description": method_description.strip(),
                        }
                    )
            return tool_info

        for name, method in inspect.getmembers(tool, predicate=inspect.ismethod):
            # 根據裝飾器判斷是否應忽略此方法
            # Check if the method should be ignored based on its decorator
            if not name.startswith("_") and not hasattr(method, "__wrapped__"):
                # 取得方法簽名
                # Get the method signature
                method_signature = inspect.signature(method)
                # 構建不含 *args 和 **kwargs 的簽名字串
                # Construct the signature string without *args and **kwargs
                param_str = ", ".join(
                    f"{param.name}"
                    if param.default == param.empty
                    else f"{param.name}={param.default!r}"
                    for param in method_signature.parameters.values()
                    if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
                )
                full_signature = (
                    f"computer.{tool.__class__.__name__.lower()}.{name}({param_str})"
                )
                # 取得方法描述
                # Get the method description
                method_description = method.__doc__ or ""
                # 附加方法詳細資訊
                # Append the method details
                tool_info["methods"].append(
                    {
                        "signature": full_signature,
                        "description": method_description.strip(),
                    }
                )
        return tool_info

    def run(self, *args, **kwargs):
        """
        Shortcut for computer.terminal.run
        """
        return self.terminal.run(*args, **kwargs)

    def exec(self, code):
        """
        Shortcut for computer.terminal.run("shell", code)
        It has hallucinated this.
        """
        return self.terminal.run("shell", code)

    def stop(self):
        """
        Shortcut for computer.terminal.stop
        """
        return self.terminal.stop()

    def terminate(self):
        """
        Shortcut for computer.terminal.terminate
        """
        return self.terminal.terminate()

    def screenshot(self, *args, **kwargs):
        """
        Shortcut for computer.display.screenshot
        """
        return self.display.screenshot(*args, **kwargs)

    def view(self, *args, **kwargs):
        """
        Shortcut for computer.display.screenshot
        """
        return self.display.screenshot(*args, **kwargs)

    def to_dict(self):
        def json_serializable(obj):
            try:
                json.dumps(obj)
                return True
            except:
                return False

        return {k: v for k, v in self.__dict__.items() if json_serializable(v)}

    def load_dict(self, data_dict):
        for key, value in data_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
