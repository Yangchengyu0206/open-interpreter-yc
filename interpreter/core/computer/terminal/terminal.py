import json
import os
import time
import subprocess
import getpass

from ..utils.recipient_utils import parse_for_recipient
from .languages.applescript import AppleScript
from .languages.html import HTML
from .languages.java import Java
from .languages.javascript import JavaScript
from .languages.powershell import PowerShell
from .languages.python import Python
from .languages.r import R
from .languages.react import React
from .languages.ruby import Ruby
from .languages.shell import Shell

# 這個類別應該改名為 OS 或 System 嗎？
# Should this be renamed to OS or System?

import_computer_api_code = """
import os
# 防止無限遞迴匯入 computer API
os.environ["INTERPRETER_COMPUTER_API"] = "False" # To prevent infinite recurring import of the computer API

import time
import datetime
from interpreter import interpreter

computer = interpreter.computer
""".strip()


class Terminal:
    def __init__(self, computer):
        self.computer = computer
        self.languages = [
            Ruby,
            Python,
            Shell,
            JavaScript,
            HTML,
            AppleScript,
            R,
            PowerShell,
            React,
            Java,
        ]
        self._active_languages = {}

    def sudo_install(self, package):
        try:
            # 首先嘗試不使用 sudo 安裝
            # First, try to install without sudo
            subprocess.run(['apt', 'install', '-y', package], check=True)
        except subprocess.CalledProcessError:
            # 若失敗，改用 sudo 安裝
            # If it fails, try with sudo
            print(f"Installation of {package} requires sudo privileges.")
            sudo_password = getpass.getpass("Enter sudo password: ")

            try:
                # 使用 sudo 加密碼進行安裝
                # Use sudo with password
                subprocess.run(
                    ['sudo', '-S', 'apt', 'install', '-y', package],
                    input=sudo_password.encode(),
                    check=True
                )
                print(f"Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package}. Error: {e}")
                return False

        return True

    def get_language(self, language):
        for lang in self.languages:
            if language.lower() == lang.name.lower() or (
                hasattr(lang, "aliases")
                and language.lower() in (alias.lower() for alias in lang.aliases)
            ):
                return lang
        return None

    def run(self, language, code, stream=False, display=False):
        # 檢查是否為 apt install 指令
        # Check if this is an apt install command
        if language == "shell" and code.strip().startswith("apt install"):
            package = code.split()[-1]
            if self.sudo_install(package):
                return [{"type": "console", "format": "output", "content": f"Package {package} installed successfully."}]
            else:
                return [{"type": "console", "format": "output", "content": f"Failed to install package {package}."}]

        if language == "python":
            if (
                self.computer.import_computer_api
                and not self.computer._has_imported_computer_api
                and "computer" in code
                and os.getenv("INTERPRETER_COMPUTER_API", "True") != "False"
            ):
                self.computer._has_imported_computer_api = True
                # 透過 Python 賦予其存取 computer 的能力
                # Give it access to the computer via Python
                time.sleep(0.5)
                self.computer.run(
                    language="python",
                    code=import_computer_api_code,
                    display=self.computer.verbose,
                )

            if self.computer.import_skills and not self.computer._has_imported_skills:
                self.computer._has_imported_skills = True
                self.computer.skills.import_skills()

            # 此方法無法運作，因為被截斷的程式碼儲存在 interpreter.messages 中 :/
            # 若儲存了完整的程式碼，我們可以這樣做：
            # This won't work because truncated code is stored in interpreter.messages :/
            # If the full code was stored, we could do this:
            if False and "get_last_output()" in code:
                if "# We wouldn't want to have maximum recursion depth!" in code:
                    # 我們剛剛才嘗試執行這段，稍後再說
                    # We just tried to run this, in a moment.
                    pass
                else:
                    code_outputs = [
                        m
                        for m in self.computer.interpreter.messages
                        if m["role"] == "computer"
                        and "content" in m
                        and m["content"] != ""
                    ]
                    if len(code_outputs) > 0:
                        last_output = code_outputs[-1]["content"]
                    else:
                        last_output = ""
                    last_output = json.dumps(last_output)

                    self.computer.run(
                        "python",
                        f"# We wouldn't want to have maximum recursion depth!\nimport json\ndef get_last_output():\n    return '''{last_output}'''",
                    )

        if stream == False:
            # 若 stream == False，則主動從 _streaming_run 拉取資料
            # If stream == False, *pull* from _streaming_run.
            output_messages = []
            for chunk in self._streaming_run(language, code, display=display):
                if chunk.get("format") != "active_line":
                    # 是否應追加至最後一則訊息，還是建立新訊息？
                    # Should we append this to the last message, or make a new one?
                    if (
                        output_messages != []
                        and output_messages[-1].get("type") == chunk["type"]
                        and output_messages[-1].get("format") == chunk["format"]
                    ):
                        output_messages[-1]["content"] += chunk["content"]
                    else:
                        output_messages.append(chunk)
            return output_messages

        elif stream == True:
            # 若 stream == True，以 _streaming_run 取代
            # If stream == True, replace this with _streaming_run.
            return self._streaming_run(language, code, display=display)

    def _streaming_run(self, language, code, display=False):
        if language not in self._active_languages:
            # 取得語言。若其 __init__ 只接受一個參數則傳入 self.computer，
            # 否則不傳入任何參數。這讓自訂語言更容易加入與理解。
            # Get the language. Pass in self.computer *if it takes a single argument*
            # but pass in nothing if not. This makes custom languages easier to add / understand.
            lang_class = self.get_language(language)
            if lang_class.__init__.__code__.co_argcount > 1:
                self._active_languages[language] = lang_class(self.computer)
            else:
                self._active_languages[language] = lang_class()
        try:
            for chunk in self._active_languages[language].run(code):
                # self.format_to_recipient 可將部分訊息格式化為指定收件人。
                # 在此將其加入 LMC 訊息：
                # self.format_to_recipient can format some messages as having a certain recipient.
                # Here we add that to the LMC messages:
                if chunk["type"] == "console" and chunk.get("format") == "output":
                    recipient, content = parse_for_recipient(chunk["content"])
                    if recipient:
                        chunk["recipient"] = recipient
                        chunk["content"] = content

                    # 有時我們想隱藏 traceback 以節省 token。
                    # （這是個好主意嗎？）
                    # Sometimes, we want to hide the traceback to preserve tokens.
                    # (is this a good idea?)
                    if "@@@HIDE_TRACEBACK@@@" in content:
                        chunk["content"] = (
                            "Stopping execution.\n\n"
                            + content.split("@@@HIDE_TRACEBACK@@@")[-1].strip()
                        )

                yield chunk

                # 若 display = True，同時列印輸出
                # Print it also if display = True
                if (
                    display
                    and chunk.get("format") != "active_line"
                    and chunk.get("content")
                ):
                    print(chunk["content"], end="")

        except GeneratorExit:
            self.stop()

    def stop(self):
        for language in self._active_languages.values():
            language.stop()

    def terminate(self):
        for language_name in list(self._active_languages.keys()):
            language = self._active_languages[language_name]
            if (
                language
            # 不確定為什麼這有時是 None，應該調查一下
            ):  # Not sure why this is None sometimes. We should look into this
                language.terminate()
            del self._active_languages[language_name]
