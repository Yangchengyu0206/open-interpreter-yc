import os

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import sys

# 注意：litellm 在 DEV 模式下會從當前目錄及所有父目錄讀取 .env 檔案。
# 若父資料夾中存在 .env 檔案，可能導致非預期的 API 金鑰被載入。
# Note: litellm in DEV mode will load .env files from the current directory
# and all parent directories. This can lead to unexpected API keys being loaded
# if there are .env files in parent folders.
import litellm

litellm.suppress_debug_info = True
litellm.REPEATED_STREAMING_CHUNK_LIMIT = 99999999

import json
import logging
import subprocess
import time
import uuid

import requests
import tokentrim as tt

from .run_text_llm import run_text_llm

# from .run_function_calling_llm import run_function_calling_llm
from .run_tool_calling_llm import run_tool_calling_llm
from .utils.convert_to_openai_messages import convert_to_openai_messages

# 建立或取得 logger
# Create or get the logger
logger = logging.getLogger("LiteLLM")


class SuppressDebugFilter(logging.Filter):
    def filter(self, record):
        # 只抑制包含特定關鍵字的訊息
        # Suppress only the specific message containing the keywords
        if "cost map" in record.getMessage():
            # 抑制此 log 訊息
            return False  # Suppress this log message
        # 允許所有其他訊息
        return True  # Allow all other messages


class Llm:
    """
    對 LiteLLM 的包裝：以 LMC 風格訊息串流呼叫模型（類別本身不持久保存對話狀態，狀態在 interpreter.messages）。
    """

    def __init__(self, interpreter):
        # 將過濾器加入 logger
        # Add the filter to the logger
        logger.addFilter(SuppressDebugFilter())

        # 儲存對父 interpreter 的參考
        # Store a reference to parent interpreter
        self.interpreter = interpreter

        # OpenAI 相容的聊天補全「端點」
        # OpenAI-compatible chat completions "endpoint"
        self.completions = fixed_litellm_completions

        # 設定
        # Settings
        self.model = "gpt-4o"
        self.temperature = 0.0

        # 嘗試自動偵測是否支援視覺
        self.supports_vision = None  # Will try to auto-detect
        self.vision_renderer = (
            self.interpreter.computer.vision.query
        # 僅在 supports_vision 為 False 時使用
        )  # Will only use if supports_vision is False

        # 嘗試自動偵測是否支援函式呼叫
        self.supports_functions = None  # Will try to auto-detect
        # 若 supports_functions 為 False，此字串會附加至 system message
        self.execution_instructions = "To execute code on the user's machine, write a markdown code block. Specify the language after the ```. You will receive the output. Use any programming language."  # If supports_functions is False, this will be added to the system message

        # 可選設定
        # Optional settings
        self.context_window = None
        self.max_tokens = None
        self.api_base = None
        self.api_key = None
        self.api_version = None
        self._is_loaded = False

        # 由 LiteLLM 驅動的預算管理員
        # Budget manager powered by LiteLLM
        self.max_budget = None

    def run(self, messages):
        """
        We're responsible for formatting the call into the llm.completions object,
        starting with LMC messages in interpreter.messages, going to OpenAI compatible messages into the llm,
        respecting whether it's a vision or function model, respecting its context window and max tokens, etc.

        And then processing its output, whether it's a function or non function calling model, into LMC format.
        """

        if not self._is_loaded:
            self.load()

        if (
            self.max_tokens is not None
            and self.context_window is not None
            and self.max_tokens > self.context_window
        ):
            print(
                "Warning: max_tokens is larger than context_window. Setting max_tokens to be 0.2 times the context_window."
            )
            self.max_tokens = int(0.2 * self.context_window)

        # 基本斷言
        # Assertions
        assert (
            messages[0]["role"] == "system"
        ), "First message must have the role 'system'"
        for msg in messages[1:]:
            assert (
                msg["role"] != "system"
            ), "No message after the first can have the role 'system'"

        model = self.model
        if model in [
            "claude-3.5",
            "claude-3-5",
            "claude-3.5-sonnet",
            "claude-3-5-sonnet",
        ]:
            model = "claude-3-5-sonnet-20240620"
            self.model = "claude-3-5-sonnet-20240620"
        # 設置我們的模型端點
        # Setup our model endpoint
        if model == "i":
            model = "openai/i"
            # 只執行一次
            if not hasattr(self.interpreter, "conversation_id"):  # Only do this once
                self.context_window = 7000
                self.api_key = "x"
                self.max_tokens = 1000
                self.api_base = "https://api.openinterpreter.com/v0"
                self.interpreter.conversation_id = str(uuid.uuid4())

        # 偵測函式呼叫支援
        # Detect function support
        if self.supports_functions == None:
            try:
                if litellm.supports_function_calling(model):
                    self.supports_functions = True
                else:
                    self.supports_functions = False
            except:
                self.supports_functions = False

        # 偵測視覺支援
        # Detect vision support
        if self.supports_vision == None:
            try:
                if litellm.supports_vision(model):
                    self.supports_vision = True
                else:
                    self.supports_vision = False
            except:
                self.supports_vision = False

        # 若存在圖片訊息則進行裁剪
        # Trim image messages if they're there
        image_messages = [msg for msg in messages if msg["type"] == "image"]
        if self.supports_vision:
            if self.interpreter.os:
                # 若 interpreter 運行在 OS 模式下，只保留最後兩張圖片
                # Keep only the last two images if the interpreter is running in OS mode
                if len(image_messages) > 1:
                    for img_msg in image_messages[:-2]:
                        messages.remove(img_msg)
                        if self.interpreter.verbose:
                            print("Removing image message!")
            else:
                # 刪除中間的圖片（只保留第一張及最後兩張），以減少傳給 LLM 的 token 數
                # Delete all the middle ones (leave only the first and last 2 images) from messages_for_llm
                if len(image_messages) > 3:
                    for img_msg in image_messages[1:-2]:
                        messages.remove(img_msg)
                        if self.interpreter.verbose:
                            print("Removing image message!")
                # 未來可考慮將中間訊息設為 detail: low，而非直接刪除
                # Idea: we could set detail: low for the middle messages, instead of deleting them
        elif self.supports_vision == False and self.vision_renderer:
            for img_msg in image_messages:
                if img_msg["format"] != "description":
                    self.interpreter.display_message("\n  *Viewing image...*\n")

                    if img_msg["format"] == "path":
                        precursor = f"The image I'm referring to ({img_msg['content']}) contains the following: "
                        if self.interpreter.computer.import_computer_api:
                            postcursor = f"\nIf you want to ask questions about the image, run `computer.vision.query(path='{img_msg['content']}', query='(ask any question here)')` and a vision AI will answer it."
                        else:
                            postcursor = ""
                    else:
                        precursor = "Imagine I have just shown you an image with this description: "
                        postcursor = ""

                    try:
                        image_description = self.vision_renderer(lmc=img_msg)
                        ocr = self.interpreter.computer.vision.ocr(lmc=img_msg)

                        # 未來可考慮將此格式化為「I see: image_description」顯示給使用者
                        # It would be nice to format this as a message to the user and display it like: "I see: image_description"

                        img_msg["content"] = (
                            precursor
                            + image_description
                            + "\n---\nI've OCR'd the image, this is the result (this may or may not be relevant. If it's not relevant, ignore this): '''\n"
                            + ocr
                            + "\n'''"
                            + postcursor
                        )
                        img_msg["format"] = "description"

                    except ImportError:
                        print(
                            "\nTo use local vision, run `pip install 'open-interpreter[local]'`.\n"
                        )
                        img_msg["format"] = "description"
                        img_msg["content"] = ""

        # 轉換為 OpenAI 訊息格式
        # Convert to OpenAI messages format
        messages = convert_to_openai_messages(
            messages,
            function_calling=self.supports_functions,
            vision=self.supports_vision,
            shrink_images=self.interpreter.shrink_images,
            interpreter=self.interpreter,
        )

        system_message = messages[0]["content"]
        messages = messages[1:]

        # 裁剪訊息長度
        # Trim messages
        try:
            if self.context_window and self.max_tokens:
                trim_to_be_this_many_tokens = (
                    self.context_window - self.max_tokens - 25
                # 任意緩衝值
                )  # arbitrary buffer
                messages = tt.trim(
                    messages,
                    system_message=system_message,
                    max_tokens=trim_to_be_this_many_tokens,
                )
            elif self.context_window and not self.max_tokens:
                # 若未設定 max_tokens，則直接裁剪至 context_window 大小
                # Just trim to the context window if max_tokens not set
                messages = tt.trim(
                    messages,
                    system_message=system_message,
                    max_tokens=self.context_window,
                )
            else:
                try:
                    messages = tt.trim(
                        messages, system_message=system_message, model=model
                    )
                except:
                    if len(messages) == 1:
                        if self.interpreter.in_terminal_interface:
                            self.interpreter.display_message(
                                """
**We were unable to determine the context window of this model.** Defaulting to 8000.

If your model can handle more, run `interpreter --context_window {token limit} --max_tokens {max tokens per response}`.

Continuing...
                            """
                            )
                        else:
                            self.interpreter.display_message(
                                """
**We were unable to determine the context window of this model.** Defaulting to 8000.

If your model can handle more, run `self.context_window = {token limit}`.

Also please set `self.max_tokens = {max tokens per response}`.

Continuing...
                            """
                            )
                    messages = tt.trim(
                        messages, system_message=system_message, max_tokens=8000
                    )
        except:
            # 若我們正在裁剪訊息，此操作可能不起作用。
            # 若我們裁剪的是未知的模型，此操作可能不起作用。
            # 在 `messages` 超出限制之前，最好不要失敗，以避免造成挫敗感。
            # If we're trimming messages, this won't work.
            # If we're trimming from a model we don't know, this won't work.
            # Better not to fail until `messages` is too big, just for frustrations sake, I suppose.

            # 將 system message 重新合併至訊息列表
            # Reunite system message with messages
            messages = [{"role": "system", "content": system_message}] + messages

            pass

        # 若應存在 system message，就必須確保它存在！
        # 空的 system message 似乎會被刪除 :(
        # If there should be a system message, there should be a system message!
        # Empty system messages appear to be deleted :(
        if system_message == "":
            if messages[0]["role"] != "system":
                messages = [{"role": "system", "content": system_message}] + messages

        ## 開始組建請求
        ## Start forming the request

        params = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        # 可選輸入
        # Optional inputs
        _api_key = self.api_key
        if isinstance(_api_key, str):
            _api_key = _api_key.strip() or None
        if _api_key:
            params["api_key"] = _api_key

        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_version:
            params["api_version"] = self.api_version
        if self.max_tokens:
            params["max_tokens"] = self.max_tokens
        if self.temperature:
            params["temperature"] = self.temperature
        if hasattr(self.interpreter, "conversation_id"):
            params["conversation_id"] = self.interpreter.conversation_id

        # 直接在 LiteLLM 上設置部分參數
        # Set some params directly on LiteLLM
        if self.max_budget:
            litellm.max_budget = self.max_budget
        if self.interpreter.verbose:
            litellm.set_verbose = True

        if (
            self.interpreter.debug == True and False  # DISABLED
        # debug 等於 "server" 代表我們正在針對伺服器進行除錯
        ):  # debug will equal "server" if we're debugging the server specifically
            print("\n\n\nOPENAI COMPATIBLE MESSAGES:\n\n\n")
            for message in messages:
                if len(str(message)) > 5000:
                    print(str(message)[:200] + "...")
                else:
                    print(message)
                print("\n")
            print("\n\n\n")

        if self.supports_functions:
            # yield from run_function_calling_llm(self, params)
            yield from run_tool_calling_llm(self, params)
        else:
            yield from run_text_llm(self, params)

    # 若更改模型，將 _is_loaded 設為 False
    # If you change model, set _is_loaded to false
    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self._model = value
        self._is_loaded = False

    def load(self):
        if self._is_loaded:
            return

        if self.model.startswith("ollama/") and not ":" in self.model:
            self.model = self.model + ":latest"

        self._is_loaded = True

        if self.model.startswith("ollama/"):
            model_name = self.model.replace("ollama/", "")
            api_base = getattr(self, "api_base", None) or os.getenv(
                "OLLAMA_HOST", "http://localhost:11434"
            )
            names = []
            try:
                # 列出所有已下載的 ollama 模型，若未安裝 ollama 則會失敗
                # List out all downloaded ollama models. Will fail if ollama isn't installed
                response = requests.get(f"{api_base}/api/tags")
                if response.ok:
                    data = response.json()
                    names = [
                        model["name"]
                        for model in data["models"]
                        if "name" in model and model["name"]
                    ]

            except Exception as e:
                print(str(e))
                self.interpreter.display_message(
                    f"> Ollama not found\n\nPlease download Ollama from [ollama.com](https://ollama.com/) to use `{model_name}`.\n"
                )
                exit()

            # 若模型尚未安裝則下載
            # Download model if not already installed
            if model_name not in names:
                self.interpreter.display_message(f"\nDownloading {model_name}...\n")
                requests.post(f"{api_base}/api/pull", json={"name": model_name})

            # 若尚未設定 context window 則取得之
            # Get context window if not set
            if self.context_window == None:
                response = requests.post(
                    f"{api_base}/api/show", json={"name": model_name}
                )
                model_info = response.json().get("model_info", {})
                context_length = None
                for key in model_info:
                    if "context_length" in key:
                        context_length = model_info[key]
                        break
                if context_length is not None:
                    self.context_window = context_length
            if self.max_tokens == None:
                if self.context_window != None:
                    self.max_tokens = int(self.context_window * 0.2)

            # 傳送 ping 以實際載入模型
            # Send a ping, which will actually load the model
            model_name = model_name.replace(":latest", "")
            print(f"Loading {model_name}...\n")

            old_max_tokens = self.max_tokens
            self.max_tokens = 1
            self.interpreter.computer.ai.chat("ping")
            self.max_tokens = old_max_tokens

            self.interpreter.display_message("*Model loaded.*\n")

        # 驗證 LLM 的邏輯應移至此處！！
        # Validate LLM should be moved here!!

        if self.context_window == None:
            try:
                model_info = litellm.get_model_info(model=self.model)
                self.context_window = model_info["max_input_tokens"]
                if self.max_tokens == None:
                    self.max_tokens = min(
                        int(self.context_window * 0.2), model_info["max_output_tokens"]
                    )
            except:
                pass


def _coerce_litellm_api_key(params):
    """新版 OpenAI client 要求在建立 client 時就帶上非空的 api_key。

    Hugging Face Inference / Router（``router.huggingface.co``）只接受 **HF Hub token**。
    若環境裡先有無效的 ``OPENAI_API_KEY``／占位 dummy，過去「優先 OPENAI」會送出錯金鑰而得到 401。
    """
    api_base_l = ((params.get("api_base") or "") + "").lower()
    uses_hf_inference = "router.huggingface.co" in api_base_l

    hf_tok = (os.getenv("HF_TOKEN") or "").strip()
    if not hf_tok:
        hf_tok = (os.getenv("HUGGINGFACE_HUB_TOKEN") or "").strip()

    # Router：一律優先環境中的 Hub token（高於占位 OPENAI_API_KEY）
    if uses_hf_inference and hf_tok:
        params["api_key"] = hf_tok
        return

    k = params.get("api_key")
    if isinstance(k, str):
        k = k.strip()
    if k:
        params["api_key"] = k
        return

    priority = (
        ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        if uses_hf_inference
        else ("OPENAI_API_KEY", "HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "ANTHROPIC_API_KEY")
    )
    for env_name in priority:
        v = (os.getenv(env_name) or "").strip()
        if v:
            params["api_key"] = v
            return
    params["api_key"] = "x"


def fixed_litellm_completions(**params):
    """
    Just uses a dummy API key, since we use litellm without an API key sometimes.
    Hopefully they will fix this!
    """

    if "local" in params.get("model"):
        # 有點 Hack，但有時有幫助
        # Kinda hacky, but this helps sometimes
        params["stop"] = ["<|assistant|>", "<|end|>", "<|eot_id|>"]

    if params.get("model") == "i" and "conversation_id" in params:
        litellm.drop_params = (
            # 若不這樣做，litellm 會丟棄此參數！
            False  # If we don't do this, litellm will drop this param!
        )
    else:
        litellm.drop_params = True

    params["model"] = params["model"].replace(":latest", "")

    _coerce_litellm_api_key(params)

    # 執行補全
    # Run completion
    attempts = 4
    first_error = None

    params["num_retries"] = 0

    for attempt in range(attempts):
        try:
            yield from litellm.completion(**params)
            return  # If the completion is successful, exit the function
        except KeyboardInterrupt:
            print("Exiting...")
            sys.exit(0)
        except Exception as e:
            if attempt == 0:
                # 儲存第一個錯誤
                # Store the first error
                first_error = e
            if isinstance(e, litellm.exceptions.AuthenticationError) and not str(
                params.get("api_key", "") or ""
            ).strip():
                print(
                    "LiteLLM requires an API key. Trying again with a dummy API key. In the future, if this fixes it, please set a dummy API key to prevent this message. (e.g `interpreter --api_key x` or `self.api_key = 'x'`)"
                )
                # 使用假的 API 金鑰再試一次
                # So, let's try one more time with a dummy API key:
                params["api_key"] = "x"
            if attempt == 1:
                # 嘗試調高 temperature？
                # Try turning up the temperature?
                params["temperature"] = params.get("temperature", 0.0) + 0.1

    if first_error is not None:
        raise first_error  # If all attempts fail, raise the first error
