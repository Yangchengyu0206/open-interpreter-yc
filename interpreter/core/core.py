"""
定義 Open Interpreter 主類別。
本檔為核心入口之一：`from interpreter import interpreter` 會載入此類別的實例。
"""
import json
import os
import threading
import time
from datetime import datetime

from ..terminal_interface.local_setup import local_setup
from ..terminal_interface.terminal_interface import terminal_interface
from ..terminal_interface.utils.display_markdown_message import display_markdown_message
from ..terminal_interface.utils.local_storage_path import get_storage_path
from ..terminal_interface.utils.oi_dir import oi_dir
from .computer.computer import Computer
from .default_system_message import default_system_message
from .llm.llm import Llm
from .respond import respond
from .utils.telemetry import send_telemetry
from .utils.truncate_output import truncate_output


class OpenInterpreter:
    """
    專案中的「總樞紐」：一個實例慣稱為 `interpreter`。

    職責概覽：

    1. 依使用者輸入呼叫語言模型。
    2. 解析模型回應，轉成 LMC 訊息。
    3. 將程式碼交給 computer 執行。
    4. 解析 computer 回傳（同樣為 LMC 訊息）。
    5. 把執行結果再送回語言模型。

    在「模型」與「本機執行」之間重複 1–5，直到：

    6. 依最後一則模型回應判斷整段流程是否結束。
    """

    def __init__(
        self,
        messages=None,
        offline=False,
        auto_run=False,
        verbose=False,
        debug=False,
        max_output=2800,
        safe_mode="off",
        shrink_images=True,
        loop=False,
        loop_message="""Proceed. You CAN run code on my machine. If the entire task I asked for is done, say exactly 'The task is done.' If you need some specific information (like username or password) say EXACTLY 'Please provide more information.' If it's impossible, say 'The task is impossible.' (If I haven't provided a task, say exactly 'Let me know what you'd like to do next.') Otherwise keep going.""",
        loop_breakers=[
            "The task is done.",
            "The task is impossible.",
            "Let me know what you'd like to do next.",
            "Please provide more information.",
        ],
        disable_telemetry=False,
        in_terminal_interface=False,
        conversation_history=True,
        conversation_filename=None,
        conversation_history_path=get_storage_path("conversations"),
        os=False,
        speak_messages=False,
        llm=None,
        system_message=default_system_message,
        custom_instructions="",
        user_message_template="{content}",
        always_apply_user_message_template=False,
        code_output_template="Code output: {content}\n\nWhat does this output mean / what's next (if anything, or are we done)?",
        empty_code_output_template="The code above was executed on my machine. It produced no text output. what's next (if anything, or are we done?)",
        code_output_sender="user",
        computer=None,
        sync_computer=False,
        import_computer_api=False,
        skills_path=None,
        import_skills=False,
        multi_line=True,
        contribute_conversation=False,
        plain_text_display=False,
    ):
        # 狀態
        self.messages = [] if messages is None else messages
        self.responding = False
        self.last_messages_count = 0

        # 設定
        self.offline = offline
        self.auto_run = auto_run
        self.verbose = verbose
        self.debug = debug
        self.max_output = max_output
        self.safe_mode = safe_mode
        self.shrink_images = shrink_images
        self.disable_telemetry = disable_telemetry
        self.in_terminal_interface = in_terminal_interface
        self.multi_line = multi_line
        self.contribute_conversation = contribute_conversation
        self.plain_text_display = plain_text_display
        # 額外設定：切換作用中行高亮，預設為 True
        self.highlight_active_line = True  # 是否高亮「正在執行」的那一行，預設 True

        # 迴圈（接上 loop_message 繼續任務）
        self.loop = loop
        self.loop_message = loop_message
        self.loop_breakers = loop_breakers

        # 對話歷史
        self.conversation_history = conversation_history
        self.conversation_filename = conversation_filename
        self.conversation_history_path = conversation_history_path

        # OS 控制模式（與 computer_use / --os 等相關）
        self.os = os
        self.speak_messages = speak_messages

        # 本機能力（執行語言、檔案、瀏覽器等）
        self.computer = Computer(self) if computer is None else computer
        self.sync_computer = sync_computer
        self.computer.import_computer_api = import_computer_api

        # 技能（skills）載入路徑等
        if skills_path:
            self.computer.skills.path = skills_path

        self.computer.import_skills = import_skills

        # LLM
        self.llm = Llm(self) if llm is None else llm

        # LLM：system／模板與輸出格式
        self.system_message = system_message
        self.custom_instructions = custom_instructions
        self.user_message_template = user_message_template
        self.always_apply_user_message_template = always_apply_user_message_template
        self.code_output_template = code_output_template
        self.empty_code_output_template = empty_code_output_template
        self.code_output_sender = code_output_sender

    def local_setup(self):
        """
        開啟精靈，讓終端使用者選擇本機模型等設定。
        """
        self = local_setup(self)

    def wait(self):
        while self.responding:
            time.sleep(0.2)
        # 只回傳自上次以來新增的訊息
        return self.messages[self.last_messages_count :]

    @property
    def anonymous_telemetry(self) -> bool:
        return not self.disable_telemetry and not self.offline

    @property
    def will_contribute(self):
        overrides = (
            self.offline or not self.conversation_history or self.disable_telemetry
        )
        return self.contribute_conversation and not overrides

    def chat(self, message=None, display=True, stream=False, blocking=True):
        try:
            self.responding = True
            if self.anonymous_telemetry:
                # 遙測只送型別不送內容
                message_type = type(message).__name__
                send_telemetry(
                    "started_chat",
                    properties={
                        "in_terminal_interface": self.in_terminal_interface,
                        "message_type": message_type,
                        "os_mode": self.os,
                    },
                )

            if not blocking:
                chat_thread = threading.Thread(
                    target=self.chat, args=(message, display, stream, True)
                )  # 第四個參數為 True 即 blocking
                chat_thread.start()
                return

            if stream:
                return self._streaming_chat(message=message, display=display)

            # 若 stream=False，則主動從串流中拉取（消費產生器）
            for _ in self._streaming_chat(message=message, display=display):
                pass

            self.responding = False
            return self.messages[self.last_messages_count :]

        except GeneratorExit:
            self.responding = False
            # 產生器正常關閉
        except Exception as e:
            self.responding = False
            if self.anonymous_telemetry:
                message_type = type(message).__name__
                send_telemetry(
                    "errored",
                    properties={
                        "error": str(e),
                        "in_terminal_interface": self.in_terminal_interface,
                        "message_type": message_type,
                        "os_mode": self.os,
                    },
                )

            raise

    def _streaming_chat(self, message=None, display=True):
        # display=True 時由 terminal_interface 內部呼叫 .chat(display=False, stream=True)，
        # 以 Rich 等包一層顯示，與純產生器不同，故直接轉交。
        if display:
            yield from terminal_interface(self, message)
            return

        # 單次對話訊息
        if message or message == "":
            # 傳入格式可為：dict、str、list（OpenAI 風格訊息列）
            if isinstance(message, dict):
                if "role" not in message:
                    message["role"] = "user"
                self.messages.append(message)
            elif isinstance(message, str):
                self.messages.append(
                    {"role": "user", "type": "message", "content": message}
                )
            elif isinstance(message, list):
                self.messages = message

            self.last_messages_count = len(self.messages)

            # 以下曾計畫在非多模態模型時阻擋 image 訊息，目前停用；多模態普及後可再啟用。
            # if not self.llm.supports_vision:
            #     for message in self.messages:
            #         if message["type"] == "image":
            #             raise Exception(
            #                 "Use a multimodal model and set `interpreter.llm.supports_vision` to True to handle image messages."
            #             )

            yield from self._respond_and_store()

            if self.conversation_history:
                if not self.conversation_filename:
                    first_few_words_list = self.messages[0]["content"][:25].split(" ")
                    if (
                        len(first_few_words_list) >= 2
                    ):  # 英文等有空白分詞
                        first_few_words = "_".join(first_few_words_list[:-1])
                    else:  # 中文等無空白分詞
                        first_few_words = self.messages[0]["content"][:15]
                    for char in '<>:"/\\|?*!\n':  # 檔名不允許的字元
                        first_few_words = first_few_words.replace(char, "")

                    date = datetime.now().strftime("%B_%d_%Y_%H-%M-%S")
                    self.conversation_filename = (
                        "__".join([first_few_words, date]) + ".json"
                    )

                if not os.path.exists(self.conversation_history_path):
                    os.makedirs(self.conversation_history_path)
                with open(
                    os.path.join(
                        self.conversation_history_path, self.conversation_filename
                    ),
                    "w",
                ) as f:
                    json.dump(self.messages, f)
            return

        raise Exception(
            "`interpreter.chat()` requires a display. Set `display=True` or pass a message into `interpreter.chat(message)`."
        )

    def _respond_and_store(self):
        """
        從 respond 串流拉取 chunk，處理分界（active_line、console、confirmation 等特例），
        並組裝後寫入 self.messages。
        """
        self.verbose = False

        def is_ephemeral(chunk):
            """不寫入長期 messages 的短生命期 chunk（例如作用中行高亮）。"""
            if "format" in chunk and chunk["format"] == "active_line":
                return True
            if chunk["type"] == "review":
                return True
            return False

        last_flag_base = None

        try:
            for chunk in respond(self):
                # 非同步／伺服器用法：檢查 stop_event
                if hasattr(self, "stop_event") and self.stop_event.is_set():
                    print("Open Interpreter stopping.")
                    break

                if chunk["content"] == "":
                    continue

                # active_line 內容為 None 表示該段程式執行結束
                if (
                    chunk.get("format") == "active_line"
                    and chunk.get("content", "") == None
                ):
                    if self.messages[-1]["role"] != "computer":
                        self.messages.append(
                            {
                                "role": "computer",
                                "type": "console",
                                "format": "output",
                                "content": "",
                            }
                        )

                # 確認執行前的特殊 chunk（不自動當成一般訊息）
                if chunk["type"] == "confirmation":
                    if last_flag_base:
                        yield {**last_flag_base, "end": True}
                        last_flag_base = None

                    if self.auto_run == False:
                        yield chunk

                    # 曾考慮在此強制附加空輸出以利辨識「無輸出」；保留註解區塊備查。
                    # self.messages.append(
                    #     {
                    #         "role": "computer",
                    #         "type": "console",
                    #         "format": "output",
                    #         "content": "",
                    #     }
                    # )
                    continue

                # 判斷是否延續同一則串流訊息（role/type/format）
                if (
                    last_flag_base
                    and "role" in chunk
                    and "type" in chunk
                    and last_flag_base["role"] == chunk["role"]
                    and last_flag_base["type"] == chunk["type"]
                    and (
                        "format" not in last_flag_base
                        or (
                            "format" in chunk
                            and chunk["format"] == last_flag_base["format"]
                        )
                    )
                ):
                    # 相接同一訊息（短生命期的 active_line 等由 is_ephemeral 排除）
                    if not is_ephemeral(chunk):
                        if any(
                            [
                                (property in self.messages[-1])
                                and (
                                    self.messages[-1].get(property)
                                    != chunk.get(property)
                                )
                                for property in ["role", "type", "format"]
                            ]
                        ):
                            self.messages.append(chunk)
                        else:
                            self.messages[-1]["content"] += chunk["content"]
                else:
                    if last_flag_base:
                        yield {**last_flag_base, "end": True}

                    last_flag_base = {"role": chunk["role"], "type": chunk["type"]}

                    # console 類型不強制帶 format，以便兼容 active_line 與 output
                    if "format" in chunk and chunk["type"] != "console":
                        last_flag_base["format"] = chunk["format"]

                    yield {**last_flag_base, "start": True}

                    if not is_ephemeral(chunk):
                        self.messages.append(chunk)

                yield chunk

                if chunk["type"] == "console" and chunk["format"] == "output":
                    self.messages[-1]["content"] = truncate_output(
                        self.messages[-1]["content"],
                        self.max_output,
                        add_scrollbars=self.computer.import_computer_api,
                    )

            if last_flag_base:
                yield {**last_flag_base, "end": True}
        except GeneratorExit:
            raise

    def reset(self):
        self.computer.terminate()  # 結束各語言直譯／子程序
        self.computer._has_imported_computer_api = False
        self.messages = []
        self.last_messages_count = 0

    def display_message(self, markdown):
        # 供 profile 的 start_script 等呼叫
        if self.plain_text_display:
            print(markdown)
        else:
            display_markdown_message(markdown)

    def get_oi_dir(self):
        return oi_dir
